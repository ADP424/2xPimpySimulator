# Web ↔ Bot Parity — Status & Remaining Work

Branch: `web-bot-parity` (off `stats-and-strays` @ `f5ec57e`), 19 commits, not pushed.
All 1955 tests pass (`uv run pytest`).

## Done

- **Layering**: vet SQL moved into `src/database`; server-event participation no longer opens sessions in `src/game`;
  web/bot no longer import `src.database`. Shared rules now in `src/game`: injury labels, breeding status,
  server-event menu availability, owner-event outcome text, pooch timeline, server lookups.
- **Ownership checks before charging**: treat/diagnose injuries & mutations, medical exam, cast out (also refuses dead pooches).
- **Bot fixes**: Treat Injury no longer leaks hidden injury names. Bot output otherwise unchanged (verified byte-for-byte for event outcomes and timeline).
- **Web no longer over-shows**: exact health/cooldown, other players' balances, hidden condition names, stat parameters,
  outcome chances, server-event filters/scoring. (Vendor markup and auction high bidder deliberately **kept** for now.)
- **New web pages**: Injuries & Diseases encyclopedias, Patient Room (treat / diagnose / medical exam), Events
  (pending + history + respond), Server Event (menus + participate), pooch Owner/Conditions/Timeline/Cast Out,
  kennel Messiness + Clean, real breeding result, navbar Events + bones, town season.

## To get it running (not done yet)

1. **Database**: `docker-compose up -d`. No schema or resource changes on this branch, so **no reset needed** (`main.py -r` would wipe data).
   Commands run from the repo root: the entry point is `main.py` there (not `src/main.py`; CLAUDE.md now matches).
2. **Dependencies**: already installed in this venv. On a fresh machine: `uv pip install -e .`, `-r requirements.txt`, `-r src/web/requirements.txt`, `-r requirements-dev.txt`.
3. **JS bundle**: `cd src/web/static/js && npm install && npm run build`. `app.bundle.js` is gitignored, so this must be rebuilt on every deploy.
4. **Env vars** for the web app: `SECRET_KEY`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `WEBHOOK_SECRET`.
5. **Run**: `uv run python main.py` (bot) and `uv run python main.py -w` (web).
   The bot runs a day change on startup (ages pooches, births pending puppies); add `-s` to skip it while testing.

## Still to verify by hand (needs the DB + a logged-in browser)

- [ ] Click through every new page: `/info/clinic` → Patient Room, Injuries, Diseases; `/events/`; `/events/server`; a pooch page; a kennel page; breeding.
- [ ] Vet actions deduct money and the navbar balance updates.
- [ ] Cast out sends the pooch to the park; Clean resets messiness to 0.
- [ ] Trigger an owner event (`/trigger_event`) and respond on the web; check the outcome text matches the bot.
- [ ] Trigger a server event and participate from the web (with and without a pooch).
- [ ] Bot: Treat Injury shows the symptom for a hidden injury; cast-out message; breeding status labels; timeline.
- [ ] Over-show spot-check in devtools: `/api/pooches/<id>`, `/api/breeds`, `/api/events/pending`, `/api/server-event` show no health/cooldown numbers, balances, hidden names, chances or scoring.
- [ ] Try vet actions / cast out on another player's pooch → "That's not your pooch.", no money charged.

## Next feature (on hold)

**Raw-stats exam ("uber detailed")** — a paid vet service showing exact stat numbers. Decided so far:
- Reveals the 8 core stats + size (same set as the banded Medical Exam, as numbers).
- Both bot and web get it.
- Timeline records that it happened, **without** the numbers.
- **Still to decide: price** (banded exam is $50).

## Known limitations (accepted)

- Chain events started by a web response aren't DMed by the bot; they show on the web Events page and in `/pending_events`.
- Participating from the web doesn't refresh the public Discord server-event message's participant count until the next bot-side participation.

## Pre-existing issues found (not fixed — out of scope)

- **No disease data**: `resources/diseases/` only exists on the unmerged `origin/lots-of-changes` branch (commit `7463b38`), so the
  diseases table is empty, the Diseases page shows nothing and no pooch can catch a disease. Same branch also holds
  `injuries/psychological/cannibalism_guilt`, `mutations/limb_deformities/razor_tail` and `items/` (no loader here yet).
  Decide: merge that branch, or cherry-pick `resources/diseases` and run `load_diseases()` alone (no reset).

- Rename pooch/kennel API endpoints don't check ownership.
- `auction/sale_detail.html` and `bounty_detail.html` compare 64-bit Discord IDs in JS (`===` on numbers loses precision).
- Bot: `kennels.py` calls `rename_pooch` without the name; `church.py` compares the custom-summon string to an int.
- Lint: 8 flake8 warnings (4 unused re-exports in `database/__init__.py`, 4 `l` variable names in auction routes) and 2 black hunks in the auction routes — all predate this branch.
- `src/game` still imports snapshot constants / ORM types from `src.database.models`, and `arena.py`, `actions.py`, `coordinator.py` still use `session_scope` (CLAUDE.md says they shouldn't).
- Bot `events.py` keeps `detail_entries` / `signed` only for their re-exports and tests; nothing uses them anymore.
- CLAUDE.md is a little stale (says DaisyUI v4; mentions a `/pooch/<id>/embed` route that no longer exists).
