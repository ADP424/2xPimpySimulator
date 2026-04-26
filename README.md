# Disclaimer
README updated as of 4/1/2026.

# Pimpy Simulator

A Discord bot (with optional companion website) where players manage virtual dog kennels. Collect pooches, breed them, manage their health, and watch them live — and die — as days pass.

## Gameplay Overview

Players interact through Discord slash commands and button-driven menus. Each player has:

- **Dollars**, **Bloodskulls**, and **Bones** — three in-game currencies
- **Kennels** — named containers for pooches (default capacity: 10, upgradeable to 25)
- **A graveyard** — where deceased pooches are remembered

### Pooches

Each pooch has:
- A name, sex, age, size, and mood
- Base health, and health loss from age (starting at age 5)
- Eight heritable stats: strength, cuteness, fluffiness, intelligence, dexterity, fertility, aggressiveness, and constitution (base range 8–12)
- One or more **breeds** (e.g. Toy Poodle, German Shepherd)
- Zero or more **mutations** that affect health and behavior
- Zero or more **injuries** with severity and persistence
- A breeding cooldown after reproducing (10 days, reduced by fertility)

Pooch health is the sum of its base health plus all mutation health impacts. Pooches below 5 health have a 20% chance of dying each day per point under the threshold.

### Day Change

Once per day the bot automatically:
1. **Resolves births** — pregnant pooches deliver litters (single, twins 25%, triplets 5%)
2. **Ages all pooches** — reducing health as they get older
3. **Rolls for deaths** — pooches below a health threshold have a chance to die; the cause is attributed to their most harmful mutation
4. **Processes on-death effects** — some mutations `kill`, `spread`, or `spread_all` mutations to kennel-mates when a pooch dies
5. **Restocks vendors** — 3 NPC vendors per server refresh with new pooches for sale
6. **Assigns moods** — pooches get a mood based on their health and age
7. **Triggers stray events** — wild dogs in parks have a 50% daily chance of something happening to them
8. **Triggers server events** — one server-wide event per day

### Events

Three event systems run alongside the day cycle:

- **Owner events** — player-specific events (fortune, misfortune, breeding, supernatural, debt, mutation) that trigger with a ~15% hourly chance. Max 5 active per owner, 24-hour default timeout.
- **Server events** — server-wide events everyone can participate in (arena fights, contests, community emergencies). One triggers per day.
- **Stray events** — things that happen to wild dogs in the park (encounters, illness, fortune, misfortune, mutation). 50% daily chance per stray.

### Town

Use `/town` to visit:
- **Vendors** — browse and buy pooches from rotating NPC stalls
- **Veterinary Clinic** — diagnose injuries ($25) and hidden mutations ($50), treat injuries, or look up all available breeds and mutations

### Breeding

From a pooch's info panel, players can select a compatible mate from their kennel. The resulting puppies are born the following day.

Breeding between related pooches (incest) triggers 3 extra mutation rolls on the offspring.

### Fighting

Pooches can fight in structured 3-round bouts. Attack and defense are calculated from weighted combinations of strength, size, dexterity, aggressiveness, and constitution. Fatigue accumulates each round (mitigated by constitution), and fights produce bite/scratch injuries of varying severity.

### Rituals

Players can sacrifice pooches for **bloodskulls** (base 8, doubled if the pooch is a virgin, reduced for low health) and spend bloodskulls to summon new pooches (20 base + 1 per extra roll).

### The Park

Players can spend **bones** to visit the park and catch **stray** pooches. Strays live outside kennels and have their own event system.

### Auctions

Players can list pooches for sale or post bounties for pooches with specific traits. Other players can bid on listings.

## Discord Commands

| Command | Description |
|---|---|
| `/home` | View your home — currencies, kennels, and navigation |
| `/town` | Go directly to the town |
| `/set_event_channel` | Set the channel where daily event announcements are posted |
| `/pending_events` | View your active pending events |
| `/event_history` | View past event outcomes |
| `/server_event` | View the current server event |
| `/trigger_event` | *(dev only)* Manually trigger an event |
| `/get_money` | *(dev only)* Grant yourself in-game currency for testing |
| `/increment_day` | *(dev only)* Manually advance the day |
| `/pause_day_loop` | *(dev only)* Pause or resume the automatic day cycle |

## Project Structure

```
src/
├── bot/          # Discord bot — entry point, commands, and UI components
├── game/         # Core game logic — breeding, day change, events, manage_* helpers
│   └── events/   # Owner, server, and stray event logic
├── database/     # SQLAlchemy models, schema SQL, and async CRUD operations
└── web/          # Flask + SocketIO web frontend (optional)

resources/
├── breeds/           # 150+ breed definitions (JSONC), organized by category
├── mutations/        # 50+ mutation definitions (JSONC), organized by category
├── injuries/         # Injury type definitions (JSONC) — bites, scratches, burns, maiming
├── owner_events/     # Owner event definitions (JSONC)
├── server_events/    # Server-wide event definitions (JSONC)
├── stray_events/     # Stray dog event definitions (JSONC)
├── dog_names/        # Dog name pool
└── vendor_names/     # NPC vendor name pools

Documentation/
├── Breed Guide.md
├── Mutation Guide.md
├── Injury Guide.md
├── Owner Event Guide.md
├── Server Event Guide.md
├── Stray Event Guide.md
└── TODO.md

tests/               # 121 test files mirroring src/ structure
```

## Discord Application Setup

Before running anything, configure your app in the [Discord Developer Portal](https://discord.com/developers/applications).

### Bot token & intents

1. Go to your app → **Bot**
2. Copy your token for `DISCORD_TOKEN` in `.env`
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**

### Invite the bot to your server

Use the **OAuth2 → URL Generator**:

- Scopes: `bot`, `applications.commands`
- Bot permissions: `Send Messages`, `Embed Links`, `View Channels`

### Web frontend OAuth2

If using the web frontend, go to **OAuth2** and add the following under **Redirects**:

```
http://localhost:5000/auth/callback
```

Then copy your **Client ID** and **Client Secret** for `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` in `.env`.

## Setup

### Requirements

- Python 3.14+
- PostgreSQL

### Install the project

```bash
pip install -e .
```

### Install dependencies

```bash
pip install -r requirements.txt
```

For development tooling (linting, tests):

```bash
pip install -r requirements-dev.txt
```

### Environment variables

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token

# "dev" enables dev-only commands; anything else disables them
STAGE=dev

# Timezone for the daily day-change trigger (default: America/New_York)
TZ=America/New_York
```

### Database

Add the following to your `.env` file:

```env
DATABASE=foo
DB_USER=foobar
DB_HOST=localhost
DB_PASSWORD=baz
DB_PORT=5432
```

Reset the database and load static data (breeds, mutations, injuries, events, name pools):

```bash
python main.py --reset-db
```

### Run the bot

```bash
python main.py
```

#### CLI flags

| Flag | Description |
|---|---|
| `-w`, `--web-app` | Run the web app instead of the bot |
| `-r`, `--reset-db` | Reset the database and reload all resources |
| `-n`, `--update-names` | Update owner Discord display names and exit |
| `-s`, `--skip-startup-day-change` | Skip the day change that normally runs on bot startup |
| `-m`, `--refresh-moods` | Refresh all pooch moods and exit |

## Website Integration

The bot can post signed webhook payloads to a companion web app after each day change. Payloads are HMAC-SHA256 signed using `WEBHOOK_SECRET` and sent as `X-Pimpy-Signature` headers. Each payload contains birth, death, and other events for a given Discord server.

Set `WEBHOOK_URL` and `WEBHOOK_SECRET` in your environment to enable this.

## Web Frontend

A Flask + SocketIO web app lives in `src/web/` and provides a browser-based alternative to the Discord bot UI.

### Additional dependencies

```bash
pip install -r src/web/requirements.txt
```

### Additional environment variables

Add these to your `.env` file:

```env
# Flask session secret (change this in production)
SECRET_KEY=your_secret_key

# Discord OAuth2 app credentials
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
DISCORD_REDIRECT_URI=http://localhost:5000/auth/callback

# Must match WEBHOOK_SECRET set on the bot side
PIMPY_WEBHOOK_SECRET=your_hmac_secret

# Port to serve on (default: 5000)
WEB_PORT=5000

# Set to "1" to enable Flask debug mode
FLASK_DEBUG=0
```

### Run the web app

```bash
python main.py -w
```

The app will be available at `http://localhost:5000` (or whatever `WEB_PORT` is set to).

### Bot ↔ web integration

To receive day-change events on the web app, set the following on the **bot** side:

```env
WEBHOOK_URL=http://localhost:5000/webhook/day-change
WEBHOOK_SECRET=your_hmac_secret   # must match PIMPY_WEBHOOK_SECRET above
```

## Breeds & Mutations

Breeds and mutations are defined in JSONC files under `resources/`. See the [Breed Guide](Documentation/Breed%20Guide.md) and [Mutation Guide](Documentation/Mutation%20Guide.md) for the full schema, rarity tiers, and advanced options (heritability, on-death effects, value multipliers, etc.).

### Rarity tiers

Both breeds and mutations share the same eight rarity tiers:

| Tier | Relative weight |
|---|---|
| COMMON | 1000 |
| UNCOMMON | 250 |
| NOVEL | 100 |
| RARE | 50 |
| UNPRECEDENTED | 25 |
| REMARKABLE | 10 |
| EXTRAORDINARY | 5 |
| UNIQUE | 1 |

### Mutation health impacts

| Impact | Value |
|---|---|
| IMMORTALITY | +1000 |
| BRILLIANT | +5 |
| FANTASTIC | +4 |
| GREAT | +3 |
| HEALTHY | +2 |
| HELPFUL | +1 |
| NEUTRAL | 0 |
| HARMFUL | −1 |
| UNHEALTHY | −2 |
| SEVERE | −3 |
| BRUTAL | −4 |
| FATAL | −5 |
| INSTANT_DEATH | −1000 |

## Development

```bash
# Format
black src/
isort src/

# Lint
flake8 src/

# Tests
pytest
```
