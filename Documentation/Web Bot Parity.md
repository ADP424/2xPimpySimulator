# Web ↔ Bot Parity — Status & Remaining Work

Branch: `integrate-lots-of-changes` (on GitHub). It is `web-bot-parity` plus a merge of Aidan's `lots-of-changes`
(`1ec0e35`) and an in-place database upgrade (`a2682c7`). `lots-of-changes` is now fully merged and retired; nothing
should be committed to it anymore. All 2315 tests pass (`uv run pytest`), flake8 is clean on `src/` and `tests/`.

## What the merge brought in (from lots-of-changes)

- **Hourly tick** (`game/change_hour.py`): pregnancy timers → birth or miscarriage, aging on each pooch's birth hour,
  breeding-cooldown and injury-persistence rolls, disease spread/recovery, food and hunger, fights, cannibalism,
  death rolls. Bot: `/increment_hour`, `/pause_hour_loop`. Weekly change: season + major server events.
- **Items and food**: cleaning products and dog food from vendors (bot + web), kennel food stock, hand cleaning,
  bleach's health side effect, food stat bonuses.
- **Church rituals**: clone, rejuvenate, gender change, immortalize (bloodskulls + body parts); body parts drop
  from sacrifices and violent deaths.
- **Vet**: Detailed Workup ($150, exact stats with sources; hidden conditions only as symptoms; never exact health),
  Neuter, Breed Survey. **Labels**: health, hunger, kennel mess.
- **Data**: 5 diseases (the Diseases page now has content), 6 items, Cannibalism Guilt, Razor Tail; new server-event
  scoring sources (breed match, mutation match, stat target).
- Web access checks (`require_pooch_owner` / `require_kennel_owner`) and name validation.

## How conflicts were resolved

- Parity's structure won where both branches built the same thing: multi-page auction UI, `/events/server`, the
  clinic hub + Patient Room, `/api/pooches/<id>/…` vet URLs. Lots' duplicate endpoints, blueprint (it also collided
  with `/events`), templates and serializers were removed.
- Kennel cleaning is lots' hand/item cleaning only (the free clean-to-zero is gone).
- Lots' features were kept and moved into parity's layering: items (`game/manage_items.py`), access checks
  (`game/access.py`), mate choice (`breed_with_mate_choice`), neuter billing, ritual costs (`RITUAL_COSTS`).
- **One stat calculation** (`game/manage_stats.py`) replaced four diverging copies, so hunger, rejuvenation,
  immortality and female size now affect play. Medical exam, fights, scoring and mate choice use effective stats.
- Viewing any pooch is open on the web; every action needs ownership.
- Vendor markup is no longer sent to the web (lots made it internal).

## Bugs fixed during the merge

The hour loop was never started; hourly fights called a `run_fight()` that never existed; the owner-event step
imported a missing function; cooldown/persistence ticks would have run twice an hour; Detailed Workup leaked hidden
condition names; web neuter was free; immortal pooches could still breed; clones lost their size; custom summon
crashed (string vs int); 7-day server events ended after a day; moods stopped changing; bleach and food bonuses did
nothing; cannibalism was configured but never built; cleaning messages leaked the exact mess number; the bot's
breeding "eligible females" could be males; duplicate `auction_bp` registration would crash the web app.

Found while testing on the Kraft copy: the hour tick crashed on `pooch.immortal` (and silently read starvation as 0)
because the game `Pooch` lacked lots' columns; `to_pooch` had its own stat math; kennels came out of the upgrade
with no food; and with a daily (minor) and a weekly (major) server event running at once, the web Server Events page
and the bot's `/server_event` crashed (`MultipleResultsFound`) — both now show every active event, and Participate
looks its event up by ID.

## Schema changes (needed by any database older than this branch)

`web-bot-parity` itself had no schema changes. From lots-of-changes:

| Table | Change |
|---|---|
| `global_state` | + `current_hour` BIGINT NOT NULL DEFAULT 0 |
| `owners` | + `hearts`, `brains`, `eyes`, `tails`, `teeth` INT NOT NULL DEFAULT 0; + `hand_cleaned_today` BOOL NOT NULL DEFAULT false |
| `kennels` | + `food_stock` INT NOT NULL DEFAULT 0 |
| `pooches` | + `pregnancy_timer` INT NULL; `rejuvenation_count` INT DEFAULT 0; `immortal` BOOL DEFAULT false; `starvation` INT DEFAULT 0; `mess_output` INT DEFAULT 2; `consumption` INT DEFAULT 1; `birth_hour` BIGINT NULL; checks `pooch_{pregnancy_timer,starvation,mess_output,consumption,rejuvenation_count}_minimum` (≥ 0) |
| `items` (new) | item catalog: `id`, `name` (unique), `alt_name`, `category`, `description`, `rarity`, `parameters` JSONB |
| `owner_items` (new) | inventory: (`owner_discord_id` → `owners`, `item_name`) PK, `count` ≥ 0 |

New catalog rows: diseases (5), items (6), injury "Cannibalism Guilt", mutation "Razor Tail".

**Upgrading a live database** (keeps every player): `uv run python main.py --migrate`. It adds the tables, columns and
checks (DDL generated from the models), adds only the new catalog rows, gives already-pregnant pooches a pregnancy
timer, recomputes each pooch's consumption/mess output from size and breeds, and validates catalog references. Safe to
run twice. Kennels start with no food, so add `--starting-food N` to top every kennel up to at least N food units
(a kennel eats the sum of its pooches' consumption, 2–7 an hour on the Kraft data, so ~170 is a day's grace); without
it, starving pooches turn to cannibalism within hours. Verified on a copy of the Kraft database (2026-10-14): player data unchanged, second run a no-op, schema
identical to a fresh install.

## Setup

1. **Database**: `docker-compose up -d`. Fresh install: `uv run python main.py -r`. Existing data: back up, then
   `uv run python main.py --migrate`.
2. **Dependencies**: `uv pip install -e .`, `-r requirements.txt`, `-r src/web/requirements.txt`, `-r requirements-dev.txt`.
   Tests need `greenlet` (`sqlalchemy[asyncio]`).
3. **JS bundle**: `cd src/web/static/js && npm install && npm run build` (gitignored; rebuild on every deploy — the
   merge changed `app.src.js`).
4. **Env vars** for the web app: `SECRET_KEY`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `WEBHOOK_SECRET`.
5. **Run**: `uv run python main.py` (bot; add `-s` to skip the startup day change) and `uv run python main.py -w` (web).

## Going live on Kraft

1. Back up: `docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' > kraft_backup_<date>.sql`
2. Pull `integrate-lots-of-changes`, install, rebuild the JS bundle.
3. `uv run python main.py --migrate --starting-food 170`, then restart the bot and web app.

## Still to verify by hand (dev server, migrated Kraft copy)

- [ ] Hour tick runs clean on the dev server. (Fixed 2026-10-15: it crashed with `'Pooch' object has no attribute
  'immortal'` because it read game `Pooch` dataclasses, which lacked lots' columns; it now reads database rows and
  effective stats, and the game `Pooch` carries the columns so the bot embed and web show Pregnant/Immortal/Hunger.)
- [ ] Dev week loop ticks every ~30 s and advances the season each time — expected in dev, but confirm the prod interval.
- [ ] `/increment_hour` until River, Boomer, Max and Mocha give birth (15–20 ticks); hunger rises without food.
- [ ] Buy items (bot + web), feed, hand-clean and item-clean; bleach hurts the kennel; navbar balances update.
- [ ] Rituals (bot + web): costs shown match the charge; clone keeps size; immortal pooch can't breed.
- [ ] Vet: Detailed Workup shows symptoms for hidden conditions; Neuter charges on both bot and web.
- [ ] Breeding with several females in the kennel occasionally reports a distracted male.
- [ ] Over-show spot-check in devtools: `/api/pooches/<id>`, `/api/kennels`, `/api/vendors/<id>`, `/api/server-event`.
- [ ] Actions on someone else's pooch/kennel → 403 / "That's not your pooch.", nothing charged.

## Known limitations (accepted)

- Chain events started by a web response aren't DMed by the bot; they show on the web Events page and in `/pending_events`.
- Participating from the web doesn't refresh the public Discord server-event message's participant count until the next bot-side participation.
- Health-based owner-event filters and the family-tree health are SQL approximations that count mutations only.
- Web notifications show game messages' `**bold**` markers literally (`App.showNotification` is plain text).

## Older issues still open

- `auction/sale_detail.html` and `bounty_detail.html` compare 64-bit Discord IDs in JS (`===` on numbers loses precision).
- Kennels send raw `messiness` to the web next to `messiness_label` (the bot shows only the label).
- `src/game` still imports snapshot constants / ORM types from `src.database.models` (mostly type hints).
- Bot `events.py` keeps `detail_entries` / `signed` only for their re-exports and tests; nothing uses them anymore.
