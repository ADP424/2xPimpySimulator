#!/usr/bin/env bash
# Fully reset the server's (Kraft) game: back up the database to backup/, stop the bot and web app, install
# dependencies, rebuild the JS bundle, wipe every table and reload resources/ (`main.py -r`), then start the bot
# (with its startup day change, which stocks the vendors) and the web app. Players start over: their first kennel
# gets STARTING_KENNEL_FOOD when they join.
# Event channels are wiped too; set them again with /set_event_channel.
# Usage: scripts/reset.sh [--yes]      (--yes skips the "type reset" confirmation)
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIRMED=0
for arg in "$@"; do
    case "$arg" in
        --yes) CONFIRMED=1 ;;
        -h | --help) sed -n 2,7p "$0"; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p backup logs

export PATH="$HOME/.bun/bin:$PATH" # bun's default install dir, often missing from non-interactive shells
for tool in docker uv bun; do
    command -v "$tool" > /dev/null || { echo "$tool not found. Nothing was changed." >&2; exit 1; }
done
STAMP=$(date +%Y-%m-%d_%H%M%S)

if [ "$CONFIRMED" -eq 0 ]; then
    echo "This wipes EVERY player, kennel and pooch in the database and starts the game over."
    read -r -p "Type 'reset' to continue: " answer
    [ "$answer" = "reset" ] || { echo "Cancelled. Nothing was changed." >&2; exit 1; }
fi

# 1. Back up while everything still runs (pg_dump reads one consistent snapshot). If it fails, nothing is stopped.
BACKUP="backup/pimpy_before_reset_$STAMP.sql"
echo "==> Backing up the database to $BACKUP..."
if ! docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' \
    > "$BACKUP" || [ ! -s "$BACKUP" ]; then
    rm -f "$BACKUP"
    echo "Backup failed. Nothing was changed." >&2
    exit 1
fi
echo "    $(du -h "$BACKUP" | cut -f1)"

# 2. Stop the bot and web app. Signal only the top-level process of each (`uv run` passes it on to python);
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

trap 'echo "Reset failed after the game was stopped. Fix it, then rerun scripts/reset.sh, or restore the backup: $BACKUP" >&2' ERR

# 3. Install, rebuild the JS bundle (gitignored), then wipe and reload.
echo "==> Installing dependencies..."
uv pip install --quiet -e . -r requirements.txt -r src/web/requirements.txt

echo "==> Building the JS bundle..."
(cd src/web/static/js && bun install --silent && bun run build)

echo "==> Resetting the database..."
uv run python main.py -r

# 4. Start both, detached from this shell, logging to logs/. No -s: the startup day change stocks the vendors.
echo "==> Starting..."
nohup uv run python main.py >> logs/bot.log 2>&1 &
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
echo "Backup of the old game: $BACKUP"
exit $STATUS
