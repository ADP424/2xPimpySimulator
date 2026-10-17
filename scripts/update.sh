#!/usr/bin/env bash
# Update the server (Kraft): back up the database, stop the bot and web app, pull, install, rebuild the JS
# bundle, then start the bot with -s (no startup day change) and the web app with -w. The db container keeps running.
# Usage: scripts/update.sh [--migrate]      (--migrate runs `main.py --migrate` after the pull)
set -euo pipefail

cd "$(dirname "$0")/.."

MIGRATE=0
for arg in "$@"; do
    case "$arg" in
        --migrate) MIGRATE=1 ;;
        -h | --help) sed -n 2,4p "$0"; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p backup logs

export PATH="$HOME/.bun/bin:$PATH" # bun's default install dir, often missing from non-interactive shells
for tool in git docker uv bun; do
    command -v "$tool" > /dev/null || { echo "$tool not found. Nothing was stopped." >&2; exit 1; }
done
STAMP=$(date +%Y-%m-%d_%H%M%S)

# 1. Fetch first and make sure the pull will fast-forward, so a bad pull never leaves the game stopped.
echo "==> Fetching..."
git fetch --quiet
if ! git merge-base --is-ancestor HEAD '@{u}'; then
    echo "Local branch has commits the remote doesn't; can't fast-forward. Nothing was stopped." >&2
    exit 1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Tracked files have local changes; commit or stash them first. Nothing was stopped." >&2
    git status --short --untracked-files=no >&2
    exit 1
fi

# 2. Back up while everything still runs (pg_dump reads one consistent snapshot). If it fails, nothing is stopped.
BACKUP="backup/pimpy_$STAMP.sql"
echo "==> Backing up the database to $BACKUP..."
if ! docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' \
    > "$BACKUP" || [ ! -s "$BACKUP" ]; then
    rm -f "$BACKUP"
    echo "Backup failed. Nothing was stopped." >&2
    exit 1
fi
echo "    $(du -h "$BACKUP" | cut -f1)"

# 3. Stop the bot and web app. Signal only the top-level process of each (`uv run` passes it on to python);
#    main.py turns SIGTERM into a clean shutdown.
top_level_pids() {
    local pids pid ppid
    pids=$(pgrep -f "python main.py" || true)
    for pid in $pids; do
        ppid=$(ps -o ppid= -p "$pid" | tr -d ' ') || continue
        grep -qx "$ppid" <<< "$pids" || echo "$pid"
    done
}

PIDS=$(top_level_pids)
if [ -n "$PIDS" ]; then
    echo "==> Stopping:"
    ps -o pid=,args= -p "$(echo $PIDS | tr ' ' ',')" | sed 's/^/    /'
    kill -TERM $PIDS
    for _ in $(seq 30); do
        pgrep -f "python main.py" > /dev/null || break
        sleep 1
    done
    if pgrep -f "python main.py" > /dev/null; then
        echo "    Still running after 30 s; killing."
        pkill -KILL -f "python main.py" || true
    fi
else
    echo "==> Bot and web app weren't running."
fi

trap 'echo "Update failed after the game was stopped. Fix it, then rerun scripts/update.sh (backup: $BACKUP)." >&2' ERR

# 4. Pull, install, rebuild the JS bundle (gitignored), migrate if asked.
echo "==> Pulling..."
git merge --ff-only --quiet '@{u}'
git log --oneline -1 | sed 's/^/    /'

echo "==> Installing dependencies..."
uv pip install --quiet -e . -r requirements.txt -r src/web/requirements.txt

echo "==> Building the JS bundle..."
(cd src/web/static/js && bun install --silent && bun run build)

if [ "$MIGRATE" -eq 1 ]; then
    echo "==> Migrating the database..."
    uv run python main.py --migrate
fi

# 5. Start both, detached from this shell, logging to logs/.
echo "==> Starting..."
nohup uv run python main.py -s >> logs/bot.log 2>&1 &
BOT_PID=$!
nohup uv run python main.py -w >> logs/web.log 2>&1 &
WEB_PID=$!

sleep 10
STATUS=0
for entry in "bot:$BOT_PID:logs/bot.log" "web:$WEB_PID:logs/web.log"; do
    IFS=: read -r name pid log <<< "$entry"
    if kill -0 "$pid" 2> /dev/null; then
        echo "    $name running (pid $pid, log $log)"
    else
        echo "    $name exited right away; last lines of $log:" >&2
        tail -n 20 "$log" >&2
        STATUS=1
    fi
done
exit $STATUS
