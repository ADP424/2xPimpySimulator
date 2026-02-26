# Pimpy Simulator

A Discord bot (with optional companion website) where players manage virtual dog kennels. Collect pooches, breed them, manage their health, and watch them live — and die — as days pass.

## Gameplay Overview

Players interact through Discord slash commands and button-driven menus. Each player has:

- **Dollars** and **Bloodskulls** — two in-game currencies
- **Kennels** — named containers for pooches (default capacity: 10)
- **A graveyard** — where deceased pooches are remembered

### Pooches

Each pooch has:
- A name, sex, age, and base health
- One or more **breeds** (e.g. Toy Poodle, German Shepherd)
- Zero or more **mutations** that affect health and behavior
- A breeding cooldown after reproducing

Pooch health is the sum of its base health plus all mutation health impacts. Pooches with low health risk dying each day.

### Day Change

Once per day the bot automatically:
1. **Resolves births** — pregnant pooches deliver litters (single, twins 25%, triplets 5%)
2. **Ages all pooches** — reducing health as they get older
3. **Rolls for deaths** — pooches below a health threshold have a chance to die; the cause is attributed to their most harmful mutation
4. **Processes on-death effects** — some mutations `kill`, `spread`, or `spread_all` mutations to kennel-mates when a pooch dies
5. **Restocks vendors** — 3 NPC vendors per server refresh with new pooches for sale

### Town

Use `/town` to visit:
- **Vendors** — browse and buy pooches from rotating NPC stalls
- **Veterinary Clinic** — look up all available breeds and mutations

### Breeding

From a pooch's info panel, players can select a compatible mate from their kennel. The resulting puppies are born the following day.

Breeding between related pooches (incest) triggers extra mutation rolls on the offspring.

## Discord Commands

| Command | Description |
|---|---|
| `/home` | View your home — currencies, kennels, and navigation |
| `/town` | Go directly to the town |
| `/set_event_channel` | Set the channel where daily event announcements are posted |
| `/get_money` | *(dev only)* Grant yourself in-game currency for testing |

## Project Structure

```
src/
├── bot/          # Discord bot — entry point, commands, and UI components
├── game/         # Core game logic — breeding, day change, manage_* helpers
└── database/     # SQLAlchemy models, schema SQL, and async CRUD operations

resources/
├── breeds.json       # Breed definitions
├── mutations.json    # Mutation definitions
├── dog_names.txt
└── vendor_*.txt      # NPC vendor name pools

Documentation/
├── Breed Guide.md
└── Mutation Guide.md
```

## Setup

### Requirements

- Python 3.14+
- PostgreSQL

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

# "dev" enables the /get_money command; anything else disables it
STAGE=dev

# Timezone for the daily day-change trigger (default: America/New_York)
TZ=America/New_York

# Optional: companion website webhook
WEBHOOK_URL=https://your-site.example.com/webhook
WEBHOOK_SECRET=your_hmac_secret
```

### Database

Apply the schema files in `src/database/schema/` to your PostgreSQL database, then load static data (breeds, mutations, name pools):

```bash
python -m database.load.load_resources
```

### Run the bot

```bash
python -m bot
```

## Website Integration

The bot can post signed webhook payloads to a companion web app after each day change. Payloads are HMAC-SHA256 signed using `WEBHOOK_SECRET` and sent as `X-Pimpy-Signature` headers. Each payload contains birth, death, and other events for a given Discord server.

Set `WEBHOOK_URL` and `WEBHOOK_SECRET` in your environment to enable this.

## Breeds & Mutations

Breeds and mutations are defined in JSON files under `resources/`. See the [Breed Guide](Documentation/Breed%20Guide.md) and [Mutation Guide](Documentation/Mutation%20Guide.md) for the full schema, rarity tiers, and advanced options (heritability, on-death effects, value multipliers, etc.).

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
