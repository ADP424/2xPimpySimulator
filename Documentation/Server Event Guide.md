# Server Event Guide

Server events are daily community-wide occurrences on a Discord server. They come in two flavours:

- **Passive events** — fire automatically and apply server-scoped actions to pooches across the server (strays, dead, hell). No player participation required.
- **Interactive events** — present players with menus of options. Players participate over a window of time, then the event resolves and outcomes are distributed.

---

## File Layout

Server events live in `resources/server_events/**/*.jsonc`. Each **file** defines one event. Events are grouped into category subfolders. The category comes from the folder name (titleized automatically).

```jsonc
{
    "name": "string",               // required
    "description": "string",
    "flavor_text": "string",
    "severity": "string",
    "rarity": "string",
    "filter": {},                   // see Filter block
    "actions": [],                  // server-scoped; run at trigger time
    "default_actions": [],          // server-scoped; run if nobody participated
    "menus": {},                    // named option menus for interactive events
    "outcomes": []                  // distributed at resolution time
}
```

---

## Event Parameters

### `name`

The human-readable event name. Required.

### `description`

Plain-language description of the event.

### `flavor_text`

Immersive text shown when the event is announced.

### `severity`

How impactful the event appears in the UI.

- `trivial`
- `minor`
- `moderate`
- `major`
- `critical`
- `catastrophic`

### `rarity`

How likely the event is to be selected relative to other eligible server events (higher rarity = less frequent).

- `common`
- `uncommon`
- `novel`
- `rare`
- `unprecedented`
- `remarkable`
- `extraordinary`
- `unique`

---

## Filter Block

The `filter` object defines eligibility requirements. The event only fires on a server when all filter conditions pass. Omit or leave empty to make the event always eligible.

```jsonc
"filter": {
    // Aggregate counts
    "min_owners": 2,
    "max_owners": 50,
    "min_strays": 1,
    "max_strays": 20,
    "min_dead": 1,
    "max_dead": 99,
    "min_in_hell": 1,
    "max_in_hell": 99,

    // Pool-specific pooch filters (each entry must independently pass)
    "stray_pooches": [{ "min_count": 2, "sex": "female" }],
    "dead_pooches":  [{ "min_count": 1 }],
    "hell_pooches":  [{ "min_count": 1 }],

    // Per-owner sub-filter: N owners must satisfy all listed criteria
    "owners": [
        {
            "min_count": 2,
            "min_money": 50,
            "pooches": [{ "min_count": 1, "is_alive": true }]
        }
    ]
}
```

### Filter Fields

| Field | Type | Notes |
|-------|------|-------|
| `min_owners` / `max_owners` | int | Number of registered owners on the server |
| `min_strays` / `max_strays` | int | Number of alive strays |
| `min_dead` / `max_dead` | int | Number of pooches in the graveyard |
| `min_in_hell` / `max_in_hell` | int | Number of pooches condemned to Hell |
| `stray_pooches` | list | Pooch filter specs applied to the stray pool |
| `dead_pooches` | list | Pooch filter specs applied to the graveyard pool |
| `hell_pooches` | list | Pooch filter specs applied to the hell pool |
| `owners` | list | Per-owner sub-filters (see below) |

### `owners` Sub-filter

Each entry in the `owners` list is an owner filter that is applied independently. Both `min_count` and `max_count` control how many owners on the server must match.

| Field | Type | Notes |
|-------|------|-------|
| `min_count` / `max_count` | int | How many owners must satisfy this entry |
| `min_money` / `max_money` | int | Owner money range |
| `min_bloodskulls` / `max_bloodskulls` | int | Owner bloodskulls range |
| `min_pooches` / `max_pooches` | int | Number of owned pooches |
| `pooches` | list | Pooch filter specs for owned pooches |
| `graveyard_pooches` | list | Pooch filter specs for owner's graveyard |
| `hell_pooches` | list | Pooch filter specs for owner's hell-condemned pooches |

---

## Server-Scoped Actions (`actions` / `default_actions`)

Server events can fire actions at trigger time, targeting pools of pooches across the server — regardless of owner participation.

```jsonc
"actions": [
    {
        "action_type": "revive_pooch",
        "target_type": "server",
        "parameters": {
            "pool": "dead",
            "selector": "random",
            "count": 1,
            "destination": "stray",
            "save_as": "revenant"
        }
    },
    {
        "action_type": "add_mutation",
        "target_type": "server",
        "parameters": {
            "pool": "saved",
            "save_slot": "revenant",
            "selector": "all",
            "mutations": ["Sent by Death"]
        }
    }
]
```

Server-scoped actions always use `"target_type": "server"`.

### `pool`

Specifies which group of pooches to draw from.

| Value | Pooches included |
|-------|-----------------|
| `"stray"` | Alive strays on the server |
| `"dead"` | Pooches in the graveyard |
| `"in_hell"` | Pooches condemned to Hell |
| `"all_alive"` | All living pooches on the server (kennel + stray) |
| `"all"` | All pooches on the server |
| `"saved"` | Pooches previously stored in a named slot (requires `save_slot`) |

### `selector`

| Value | Behaviour |
|-------|-----------|
| `"all"` | Target every pooch in the resolved pool |
| `"random"` | Pick `count` random pooches (default `count: 1`) |
| `"first"` | Take the first `count` pooches from the pool |

### `count`

With `"random"`: picks exactly `count` pooches. If fewer exist, all are used.

### `filter`

A pooch filter spec to narrow the resolved pool before applying `selector`. Uses the same fields as stray event filters.

### `save_as` / `save_slot`

Named-slot chaining across actions:

- **`save_as`**: after resolving targets, write their IDs into `server_context.saved_slots["slot_name"]`
- **`save_slot`**: when `pool` is `"saved"`, read IDs from this named slot

```jsonc
// Revive a random hell pooch and save it as "escapee"
{ "action_type": "revive_pooch", "target_type": "server",
  "parameters": { "pool": "in_hell", "selector": "random", "save_as": "escapee" } },
// Add a mutation to the same pooch
{ "action_type": "add_mutation", "target_type": "server",
  "parameters": { "pool": "saved", "save_slot": "escapee", "selector": "all",
                  "mutations": ["Mild Possession"] } }
```

### `destination`

Used by actions that move pooches (e.g. `revive_pooch`, `create_pooch`).

| Value | Placement |
|-------|-----------|
| `"stray"` / `"town"` | Added to the stray pool |
| `"kennel"` | Placed in a random owner kennel with free space; falls back to stray if none found |
| `"vendor"` | Placed in a random vendor's stock; falls back to stray if no vendor found |
| `"graveyard"` | Moved to the graveyard |
| `"hell"` | Condemned to Hell |

### `default_actions`

`default_actions` fire instead of regular `outcomes` if the event resolves with **zero qualifying participants** (no one used any menu, or the event has no menus at all and `default_actions` is the only output). Useful for ensuring the event still has an effect even when ignored.

```jsonc
"default_actions": [
    {
        "action_type": "modify_base_health",
        "target_type": "server",
        "parameters": { "pool": "stray", "selector": "all", "min_amount": -1, "max_amount": -1 }
    }
]
```

---

## Menus (Interactive Events)

Interactive events expose named **menus** to players. Each menu has a list of options that players can submit. Menus may depend on other menus being used first.

```jsonc
"menus": {
    "enter": {
        "label": "Enter the Contest",
        "description": "Optional description shown in the UI.",
        "max_uses_per_player": 1,
        "depends_on": [],
        "options": [ /* ... */ ]
    },
    "boost": {
        "label": "Bribe the Judges",
        "max_uses_per_player": 3,
        "depends_on": ["enter"],
        "options": [ /* ... */ ]
    }
}
```

### Menu Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `label` | string | | Display name of the menu |
| `description` | string | | Optional UI description |
| `max_uses_per_player` | int or `"unlimited"` | `1` | How many times a player can submit to this menu |
| `depends_on` | list[string] | `[]` | Menu names that must be used by this player before this menu is available |
| `options` | list | | The choices players can submit |

### Menu Options

Each item in `options` is a choice a player can select.

```jsonc
{
    "label": "Submit a pooch",
    "description": "Pick one of your living pooches to enter.",
    "filter": { "min_money": 10 },
    "requires": {
        "pooch": { "filter": { "is_alive": true } }
    },
    "actions": [
        {
            "action_type": "modify_money",
            "target_type": "owner",
            "parameters": { "amount": -10 }
        }
    ],
    "scoring": {
        "aggregate": "max",
        "sources": [
            { "type": "pooch_stat", "stat": "base_health", "scale": 1.0, "pivot": 0.0, "direction": 1.0 }
        ]
    }
}
```

#### Option Fields

| Field | Type | Notes |
|-------|------|-------|
| `label` | string | Display name for this option |
| `description` | string | Optional description |
| `filter` | object | Owner filter that must pass for the option to be available (e.g. `min_money`) |
| `requires.pooch.filter` | object | Pooch filter — player must select a pooch that matches |
| `actions` | list | Owner-scoped actions executed immediately when the player submits |
| `scoring` | object | How this submission contributes to the player's score (see Scoring) |

#### Option `filter` Fields

Uses the standard owner filter fields:

| Field | Notes |
|-------|-------|
| `min_money` / `max_money` | Owner money |
| `min_bloodskulls` / `max_bloodskulls` | Owner bloodskulls |
| `min_pooches` / `max_pooches` | Number of owned pooches |
| `pooches` | Owned pooch filter specs |
| `graveyard_pooches` | Graveyard pooch filter specs |
| `hell_pooches` | Hell pooch filter specs |

### Scoring

If an option has a `scoring` block, each submission generates a numeric score. Scores are used to rank players at resolution.

```jsonc
"scoring": {
    "aggregate": "sum",
    "sources": [
        { "type": "random",     "min": 0.0, "max": 1.0 },
        { "type": "pooch_stat", "stat": "base_health", "scale": 1.0, "pivot": 10.0, "direction": 1.0 },
        { "type": "owner_stat", "stat": "money",       "scale": 0.01, "pivot": 100.0, "direction": 1.0 },
        { "type": "constant",   "value": 5.0 }
    ]
}
```

#### `aggregate`

How multiple submissions from the same player (when `max_uses_per_player > 1`) are combined:

| Value | Behaviour |
|-------|-----------|
| `"sum"` | Add all submission scores together |
| `"average"` | Average across all submissions |
| `"max"` | Keep the highest single submission |

#### `sources`

Each source contributes one term to the submission score. The total score is the sum of all source terms.

| `type` | Extra fields | Notes |
|--------|-------------|-------|
| `"random"` | `min`, `max` | Uniform random float in `[min, max]` |
| `"constant"` | `value` | Fixed float added to every submission |
| `"pooch_stat"` | `stat`, `scale`, `pivot`, `direction` | Stat-based modifier (see formula below) |
| `"owner_stat"` | `stat`, `scale`, `pivot`, `direction` | Owner-stat modifier (see formula below) |

**Stat modifier formula:** `max(0, 1.0 + (stat_value − pivot) × scale × direction)`

Valid `stat` values for `pooch_stat`: `base_health`, `strength`, `cuteness`, `fluffiness`, `intelligence`, `dexterity`, `fertility`, `aggressiveness`, `constitution`

Valid `stat` values for `owner_stat`: `money`, `bloodskulls`

---

## Outcomes

Outcomes are distributed at resolution time based on participation rank or other targets.

```jsonc
"outcomes": [
    {
        "label": "Winner",
        "message": "You won!",
        "target": "ranked_players",
        "min_rank": 1,
        "max_rank": 1,
        "chance": 1.0,
        "actions": [
            {
                "action_type": "modify_money",
                "target_type": "owner",
                "parameters": { "amount": 100 }
            }
        ]
    }
]
```

### Outcome Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `label` | string | | Display name |
| `message` | string | | Message shown to the player |
| `target` | string | `"ranked_players"` | Who this outcome applies to (see below) |
| `min_rank` / `max_rank` | int | | Rank range (inclusive); only for `"ranked_players"` |
| `chance` | float (0–1) | `1.0` | Probability this outcome fires for each qualifying player |
| `actions` | list | | Actions executed for each qualifying player/server target |

### `target` Values

| Value | Who receives the outcome |
|-------|--------------------------|
| `"ranked_players"` | Players whose rank falls in `[min_rank, max_rank]` |
| `"all_participants"` | Every player who participated in any menu |
| `"non_participants"` | Every registered owner who did **not** participate |
| `"server"` | Server-scoped outcome — actions have `target_type: "server"` |

When `target` is `"ranked_players"` or `"all_participants"` or `"non_participants"`, outcome actions must use `target_type: "owner"` (or owner-compatible pooch targets).

When `target` is `"server"`, outcome actions use `target_type: "server"` and the pool/selector conventions apply.

---

## Supported Server-Scoped Action Types

All actions with `"target_type": "server"` use the pool/selector/filter/save_as/save_slot parameters documented above.

| Action | Notes |
|--------|-------|
| `modify_base_health` | Modify base health of targeted pooches (alias: `modify_pooch_health`) |
| `modify_pooch_age` | Modify age |
| `set_pooch_age` | Set age to an exact value |
| `modify_strength` | Modify strength stat |
| `modify_cuteness` | Modify cuteness stat |
| `modify_fluffiness` | Modify fluffiness stat |
| `modify_intelligence` | Modify intelligence stat |
| `modify_dexterity` | Modify dexterity stat |
| `modify_fertility` | Modify fertility stat |
| `modify_aggressiveness` | Modify aggressiveness stat |
| `modify_constitution` | Modify constitution stat |
| `kill_pooch` | Kill targeted pooches |
| `damn_pooch` | Condemn targeted pooches to Hell |
| `revive_pooch` | Revive dead/damned pooches and route to a destination |
| `add_mutation` | Add a mutation; accepts `mutations` (list) or `mutation` (single name) |
| `remove_mutation` | Remove a mutation |
| `add_breed` | Add a breed weight |
| `remove_breed` | Remove a breed |
| `rename_pooch` | Rename targeted pooches |
| `modify_breeding_cooldown` | Modify or set breeding cooldown (alias: `set_breeding_cooldown`) |
| `release_stray` | Remove from kennel and add to stray pool |
| `enter_kennel` | Move a stray into a random owner kennel with free space |
| `enter_vendor_stock` | Move a stray into a random vendor's stock |
| `create_pooch` | Create a new pooch and route it to a destination |
| `clone_pooch` | Duplicate an existing pooch and route the clone |
| `breed_pooches` | Breed two pooches; offspring enters a destination |
| `select_pooch` | Resolve pooches and save to a named slot (no side effects) |
| `start_stray_event` | Trigger a stray event's actions in the server context |
| `start_server_event` | Chain into another server event's root-level actions |

Owner-only actions (`modify_money`, `modify_bloodskulls`, `modify_kennel_capacity`, `sell_pooch`, `buy_pooch`, `receive_stray`, `transfer_pooch`, `conjure_pooch`, `sacrifice_pooch`, `start_event`) are not supported with `target_type: "server"`.

---

## Action Parameter Reference (Server-Scoped)

### `modify_base_health` / `modify_pooch_age` / stat modifiers

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | Which pool to target |
| `selector` | string | `"all"`, `"random"`, `"first"` |
| `count` | int | Number to pick with `"random"` |
| `filter` | object | Pooch filter to narrow pool |
| `save_as` / `save_slot` | string | Named slot operations |
| `amount` | int | Fixed delta; or absolute when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | Random delta in range |
| `exclude_amount` | list[int] | Values to exclude from random range |
| `roll_once` | bool | Roll once and apply to all targets |
| `mode` | string | `"modify"` (default) or `"set"` |

### `set_pooch_age`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |
| `age` | int | **Required.** The exact age to set |

### `kill_pooch` / `damn_pooch`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |

### `revive_pooch`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | Typically `"dead"` or `"in_hell"` |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `destination` | string | `"stray"` (default), `"kennel"`, `"vendor"`, `"graveyard"`, `"hell"` |
| `save_as` / `save_slot` | string | |

### `add_mutation`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |
| `mutations` | list[string] | One or more mutation names to add; omit for random |
| `mutation` | string | Single mutation name (alternative to `mutations`) |

### `remove_mutation`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |
| `mutation` | string | Mutation name to remove; omit for random |

### `add_breed` / `remove_breed`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |
| `breed` | string | Breed name; omit for random |
| `weight` | float | Breed weight for `add_breed` (default `0.5`) |

### `rename_pooch`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |
| `name` | string | **Required.** New name |

### `modify_breeding_cooldown`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |
| `amount` | int | Fixed delta |
| `min_amount` / `max_amount` | int | Random delta range |
| `cooldown` | int or `"base"` | Legacy key — sets directly; `"base"` resets to mutation-adjusted base |

### `release_stray` / `enter_kennel` / `enter_vendor_stock`

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` / `save_slot` | string | |

For `enter_kennel`: if no owner kennel has free space, the pooch is left in place.
For `enter_vendor_stock`: if the server has no vendors, the pooch is left in place.

### `create_pooch`

Creates a new ownerless pooch.

| Parameter | Type | Notes |
|-----------|------|-------|
| `name` | string | Defaults to a generated name |
| `sex` | string | `"male"` or `"female"` — random if omitted |
| `age` | int | Default: `0` |
| `base_health` | int | |
| `breeding_cooldown` | int | |
| `breeds` | list or int | List of breed names, or int = number of random breeds to assign |
| `mutations` | list or int | List of mutation names, or int = number of random mutations |
| `destination` | string | `"stray"` (default), `"kennel"`, `"vendor"`, `"graveyard"`, `"hell"` |
| `save_as` | string | Save new pooch's ID into a named slot |

### `clone_pooch`

Duplicates an existing pooch.

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | Pool to find the source pooch in |
| `selector` | string | |
| `count` | int | |
| `filter` | object | Pooch filter for source selection |
| `name` / `sex` / `age` / `base_health` / `breeding_cooldown` | various | Override clone attributes |
| `destination` | string | Where to place the clone |
| `save_as` | string or list | Save clone and/or source into named slots |

`save_as` list form: `[{ "slot": "...", "target": "clone" | "source" }]`

### `breed_pooches`

Breeds two pooches. Offspring goes to `destination`.

| Parameter | Type | Notes |
|-----------|------|-------|
| `first_filter` / `second_filter` | object | Pooch filters for each parent |
| `require_unique` | bool | Ensure parents are different pooches (default: `true`) |
| `require_same` | bool | Both parents are the same pooch (self-breeding) |
| `destination` | string | Where offspring is placed |
| `baby_name` / `baby_age` / `baby_base_health` / `baby_breeding_cooldown` | various | Override offspring attributes |
| `save_as` | string or list | Save participants into named slots |

`save_as` list form: `[{ "slot": "...", "target": "baby" | "first_parent" | "second_parent" }]`

### `select_pooch`

Resolves pooches and saves IDs into a named slot. No side effects.

| Parameter | Type | Notes |
|-----------|------|-------|
| `pool` | string | |
| `selector` | string | |
| `count` | int | |
| `filter` | object | |
| `save_as` | string | Saves the resolved IDs into this slot |
| `save_slot` | string | Used when `pool` is `"saved"` |

### `start_stray_event`

Chains into a stray event. The stray event's actions run immediately against the server's current stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `event` | string | **Required.** Name of the stray event to trigger |

### `start_server_event`

Chains into another server event's root-level `actions`.

| Parameter | Type | Notes |
|-----------|------|-------|
| `event` | string | **Required.** Name of the server event |

---

## Resolution

Server events resolve after their active window ends.

1. **Rank participations** — players are ranked by their total score across all menu submissions.
2. **Distribute outcomes** — for each outcome, find the qualifying players (based on `target` and rank range), roll `chance`, and apply actions.
3. **Default actions** — if the event had menus but zero players participated (or zero qualified players exist), run `default_actions` instead.
4. **Store summary** — record winner/participant owner IDs and any pooch IDs affected.

---

## Cadence

- **One server event** is selected per server per day during the day-change cycle.
- Selection is rarity-weighted random sampling from all events whose filter passes.
- If no eligible event exists for a server, no server event fires that day.
- Server events fire **after** stray events and **before** vendor restock.

---

## Examples

### Passive community event — stray pool damage

```jsonc
// resources/server_events/community/stray_blight.jsonc
{
    "name": "Stray Blight",
    "description": "A sickness sweeps through the town's stray population, sapping their strength.",
    "flavor_text": "The strays whimper in the alleyways.",
    "severity": "minor",
    "rarity": "common",
    "filter": { "min_strays": 1 },
    "actions": [
        {
            "action_type": "modify_base_health",
            "target_type": "server",
            "parameters": {
                "pool": "stray",
                "selector": "all",
                "min_amount": -3,
                "max_amount": -1
            }
        }
    ]
}
```

### Passive revival event — chaining with named slots

```jsonc
// resources/server_events/community/hell_escapee.jsonc
{
    "name": "Hell Escapee",
    "description": "A condemned pooch breaks loose from the underworld and returns as a stray.",
    "severity": "major",
    "rarity": "rare",
    "filter": { "min_in_hell": 1 },
    "actions": [
        {
            "action_type": "revive_pooch",
            "target_type": "server",
            "parameters": {
                "pool": "in_hell",
                "selector": "random",
                "count": 1,
                "destination": "stray",
                "save_as": "escapee"
            }
        },
        {
            "action_type": "add_mutation",
            "target_type": "server",
            "parameters": {
                "pool": "saved",
                "save_slot": "escapee",
                "selector": "all",
                "mutations": ["Mild Possession"]
            }
        }
    ]
}
```

### Interactive event — raffle with random scoring

```jsonc
// resources/server_events/community/town_raffle.jsonc
{
    "name": "Town Raffle",
    "description": "The whole server is invited to throw a few dollars into the town raffle.",
    "severity": "minor",
    "rarity": "common",
    "filter": { "min_owners": 1 },
    "menus": {
        "enter": {
            "label": "Enter the Raffle",
            "max_uses_per_player": 1,
            "options": [
                {
                    "label": "Buy a raffle ticket",
                    "filter": { "min_money": 5 },
                    "actions": [
                        { "action_type": "modify_money", "target_type": "owner",
                          "parameters": { "amount": -5 } }
                    ],
                    "scoring": {
                        "aggregate": "sum",
                        "sources": [{ "type": "random", "min": 0.0, "max": 1.0 }]
                    }
                }
            ]
        }
    },
    "outcomes": [
        {
            "label": "Winner",
            "message": "You won the town raffle!",
            "target": "ranked_players",
            "min_rank": 1,
            "max_rank": 1,
            "actions": [
                { "action_type": "modify_money", "target_type": "owner",
                  "parameters": { "amount": 100 } }
            ]
        }
    ]
}
```

### Interactive event — pageant with pooch-stat scoring

```jsonc
// resources/server_events/contest/sunday_pageant.jsonc
{
    "name": "Sunday Pageant",
    "description": "Enter one of your pooches in today's pageant. The healthiest hound wins.",
    "severity": "minor",
    "rarity": "uncommon",
    "filter": { "min_owners": 1 },
    "menus": {
        "enter": {
            "label": "Enter the Pageant",
            "max_uses_per_player": 1,
            "options": [
                {
                    "label": "Enter a pooch",
                    "filter": { "min_money": 10 },
                    "requires": { "pooch": { "filter": { "is_alive": true } } },
                    "actions": [
                        { "action_type": "modify_money", "target_type": "owner",
                          "parameters": { "amount": -10 } }
                    ],
                    "scoring": {
                        "aggregate": "max",
                        "sources": [
                            { "type": "pooch_stat", "stat": "base_health",
                              "scale": 1.0, "pivot": 0.0, "direction": 1.0 }
                        ]
                    }
                }
            ]
        }
    },
    "outcomes": [
        {
            "label": "Champion",
            "message": "Your pooch won the pageant!",
            "target": "ranked_players",
            "min_rank": 1, "max_rank": 1,
            "actions": [
                { "action_type": "modify_money", "target_type": "owner",
                  "parameters": { "amount": 150 } }
            ]
        },
        {
            "label": "Runner-up",
            "message": "Your pooch placed as a runner-up.",
            "target": "ranked_players",
            "min_rank": 2, "max_rank": 3,
            "actions": [
                { "action_type": "modify_money", "target_type": "owner",
                  "parameters": { "amount": 50 } }
            ]
        }
    ]
}
```

### Multi-menu event with dependencies

```jsonc
{
    "name": "Talent Show",
    "severity": "moderate",
    "rarity": "uncommon",
    "filter": { "min_owners": 2 },
    "menus": {
        "register": {
            "label": "Register a Pooch",
            "max_uses_per_player": 1,
            "options": [
                {
                    "label": "Pay the entry fee",
                    "filter": { "min_money": 20 },
                    "requires": { "pooch": { "filter": { "is_alive": true } } },
                    "actions": [
                        { "action_type": "modify_money", "target_type": "owner",
                          "parameters": { "amount": -20 } }
                    ],
                    "scoring": {
                        "aggregate": "sum",
                        "sources": [
                            { "type": "pooch_stat", "stat": "cuteness",
                              "scale": 0.1, "pivot": 10.0, "direction": 1.0 }
                        ]
                    }
                }
            ]
        },
        "boost": {
            "label": "Bribe the Judges",
            "max_uses_per_player": 3,
            "depends_on": ["register"],
            "options": [
                {
                    "label": "Slip the judges a fiver",
                    "filter": { "min_money": 5 },
                    "actions": [
                        { "action_type": "modify_money", "target_type": "owner",
                          "parameters": { "amount": -5 } }
                    ],
                    "scoring": {
                        "aggregate": "sum",
                        "sources": [{ "type": "constant", "value": 1.5 }]
                    }
                }
            ]
        }
    },
    "outcomes": [
        {
            "label": "Winner",
            "message": "Your pooch stole the show!",
            "target": "ranked_players",
            "min_rank": 1, "max_rank": 1,
            "actions": [
                { "action_type": "modify_money", "target_type": "owner",
                  "parameters": { "amount": 200 } }
            ]
        }
    ],
    "default_actions": [
        {
            "action_type": "modify_base_health",
            "target_type": "server",
            "parameters": { "pool": "stray", "selector": "all", "amount": -1 }
        }
    ]
}
```
