# Stray Event Guide

Stray events fire once per server per day during the day-change cycle. They operate silently in the background — no player interaction is involved. They modify the server's stray pooch population (health, mutations, breeds, breeding, placement) via a simple list of sequential actions.

---

## Structure

Stray events live in `resources/stray_events/**/*.jsonc`. Each **file** defines one event. Events are grouped into category subfolders. The category comes from the folder name.

```jsonc
{
    "name": "string",
    "description": "string",
    "flavor_text": "string",
    "severity": "string",
    "rarity": "string",
    "triggered_only": false,
    "filter": {},
    "advanced_options": {},
    "actions": [
        {
            "action_type": "string",
            "target_type": "pooch",
            "repeat": 1,
            "parameters": {}
        }
    ]
}
```

---

## Event Parameters

### Category

Comes from the folder name (titleized automatically: `encounters` → `Encounters`).

### Name

The human-readable event name from the `name` field.

### Description

Text describing the event.

### Flavor Text

Optional extra flavor for logs or display.

### Severity

How impactful the event is.

- `TRIVIAL`
- `MINOR`
- `MODERATE`
- `MAJOR`
- `CRITICAL`
- `CATASTROPHIC`

### Rarity

How likely the event is to be selected relative to other events. Uses relative weights, not direct percentages.

- `COMMON`
- `UNCOMMON`
- `NOVEL`
- `RARE`
- `UNPRECEDENTED`
- `REMARKABLE`
- `EXTRAORDINARY`
- `UNIQUE`

### Triggered Only

If `true`, this event is excluded from normal random daily rolls and can only be started by another stray event action (`start_stray_event`).

### Filter

Eligibility requirements for the event. The event will only be triggered on a server if the filter passes. If omitted or empty, the event is always eligible.

```jsonc
"filter": {
    "min_count": 2,
    "max_count": 10,
    "pooches": [
        {
            "min_count": 1,
            "sex": "female"
        }
    ]
}
```

#### Filter Fields

| Field | Type | Notes |
|-------|------|-------|
| `min_count` | int | Minimum number of alive strays required on the server |
| `max_count` | int | Maximum number of alive strays allowed on the server |
| `pooches` | list | List of pooch filter specs (see below) — each must independently pass |

#### Pooch Filter Objects (in `filter.pooches`)

These use the same fields as owner event pooch filters, except `location` is not supported (all strays are implicitly in the stray pool):

- `min_count` / `max_count`
- `min_age` / `max_age` / `exclude_age`
- `sex`
- `min_health` / `max_health` / `exclude_health`
- `is_virgin`
- `min_breeding_cooldown` / `max_breeding_cooldown` / `exclude_breeding_cooldown`
- `has_any_breed` / `has_all_breeds` / `exclude_breeds`
- `has_any_mutation` / `has_all_mutations` / `exclude_mutations`

The `pooches` filter also determines the initial **candidate pool** for event actions. If the first entry in `pooches` contains attribute filters (beyond counts), those attributes are used to build the initial stray pool the event works with.

### Parameters

A free-form object reserved for future use.

### Actions

The list of actions executed when the event fires. Actions run in `action_order` order (determined by their position in the list). There must be at least one action.

---

## Selectors

Stray event actions use a `selector` parameter to control which strays are targeted.

| Selector | Behaviour |
|----------|-----------|
| `"random"` (default) | Pick one random stray from the candidate pool. Use `count` to pick more. |
| `"all"` | Target every stray in the candidate pool. |
| `"random_exclude"` | Target every stray **except** a randomly chosen subset. Use `count` to control how many are excluded. |
| `"all_exclude"` | Target every stray **not** matched by the action's `filter`. |

Note: Unlike for owner events, `"selected"` is not available for stray events (there is no player-driven pre-selection).

### `count` parameter

- **With `"random"`**: picks exactly `count` random strays. If fewer than `count` exist, all are used.
- **With `"random_exclude"`**: randomly excludes exactly `count` strays from the affected set. If `count` is not set or ≥ total strays, the action affects nobody.

---

## Named Slots (`save_as` / `use_saved`)

Actions execute sequentially. To carry a resolved pooch ID forward to a later action, use named slots:

- **`save_as`**: after resolving targets, write their IDs to `context.extra_data[slot]`
- **`use_saved`**: instead of resolving via `selector`, read IDs from the named slot

```jsonc
// Hurt a random stray and save it; then apply a mutation to the same stray
{
    "action_type": "modify_pooch_health",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "save_as": "victim",
        "amount": -5
    }
},
{
    "action_type": "add_mutation",
    "target_type": "pooch",
    "parameters": {
        "use_saved": "victim"
    }
}
```

Named slots persist for the lifetime of the event execution (including any chained `start_stray_event` sub-events, which inherit the same context).

---

## Supported Action Types

| Action | Notes |
|--------|-------|
| `modify_base_health` | Modify base health (alias: `modify_pooch_health`) |
| `modify_pooch_age` | Modify age |
| `modify_strength` | Modify strength stat |
| `modify_cuteness` | Modify cuteness stat |
| `modify_fluffiness` | Modify fluffiness stat |
| `modify_intelligence` | Modify intelligence stat |
| `modify_dexterity` | Modify dexterity stat |
| `modify_fertility` | Modify fertility stat |
| `modify_aggressiveness` | Modify aggressiveness stat |
| `modify_constitution` | Modify constitution stat |
| `kill_pooch` | Kill the stray |
| `damn_pooch` | Send a stray to Hell without reward |
| `revive_pooch` | Revive a dead/damned stray and route it to a destination |
| `add_mutation` | Add a mutation |
| `remove_mutation` | Remove a mutation |
| `add_breed` | Add a breed weight |
| `remove_breed` | Remove a breed |
| `create_pooch` | Create a new stray and add it to the pool |
| `clone_pooch` | Duplicate an existing stray into the pool |
| `rename_pooch` | Rename a stray |
| `modify_breeding_cooldown` | Modify or set breeding cooldown (alias: `set_breeding_cooldown`) |
| `breed_pooches` | Breed two strays; offspring enters the stray pool |
| `enter_kennel` | Move a stray into a random owner kennel with free space |
| `enter_vendor_stock` | Move a stray into a random vendor's stock |
| `start_stray_event` | Trigger another stray event, chaining its actions |

Actions **not** supported in stray events (owner-only):
`modify_money`, `modify_bloodskulls`, `modify_kennel_capacity`, `conjure_pooch`, `sacrifice_pooch`, `sell_pooch`, `buy_pooch`, `release_stray`, `receive_stray`, `transfer_pooch`, `start_event`

---

## Action Parameter Reference

Most action parameters mirror the owner event system. Only stray-specific differences are noted.

### `modify_base_health` / `modify_pooch_age`

> `modify_pooch_health` is a supported alias for `modify_base_health`.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | `"random"` (default), `"all"`, `"random_exclude"`, `"all_exclude"` |
| `count` | int | Number to pick (`"random"`) or exclude (`"random_exclude"`) |
| `filter` | object | Pooch filter to narrow the target pool |
| `amount` | int | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | Random delta in range |
| `exclude_amount` | list[int] | Exclude these values from the random range |
| `roll_once` | bool | Roll once and apply to all targets |
| `mode` | string | `"modify"` (default) or `"set"` |
| `save_as` | string | Save resolved pooch IDs into a named slot |
| `use_saved` | string | Use IDs from a named slot |

### `kill_pooch`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | `"random"`, `"all"`, `"random_exclude"`, `"all_exclude"` |
| `count` | int | Number to pick or exclude |
| `filter` | object | Pooch filter |
| `save_as` | string | Save resolved pooch IDs |
| `use_saved` | string | Use IDs from a named slot |

Killed pooches are removed from the candidate pool so later actions in the same event don't target them.

### `add_mutation` / `remove_mutation`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `mutation` | string | Mutation name — omit for a random mutation |
| `mutation_id` | int | Internal mutation ID — prefer `mutation` over this |
| `min_rarity` / `max_rarity` | string | Filter random mutation pool by rarity — values: `common`, `uncommon`, `novel`, `rare`, `unprecedented`, `remarkable`, `extraordinary`, `unique` |
| `min_health_impact` / `max_health_impact` | string | Filter random mutation pool by health impact — values: `instant_death`, `fatal`, `brutal`, `severe`, `unhealthy`, `harmful`, `neutral`, `helpful`, `healthy`, `great`, `fantastic`, `brilliant`, `immortality` |
| `save_as` / `use_saved` | string | Named slots |

Rarity and health_impact filters only apply when selecting randomly (no `mutation` / `mutation_id` given).

### `add_breed`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `breed` | string | Breed name — omit for a random breed |
| `weight` | float | Breed weight (default: `0.5`) |
| `min_rarity` / `max_rarity` | string | Filter random breed pool by rarity — values: `common`, `uncommon`, `novel`, `rare`, `unprecedented`, `remarkable`, `extraordinary`, `unique` |
| `save_as` / `use_saved` | string | Named slots |

Rarity filters only apply when no specific `breed` is given.

### `remove_breed`

Removes a breed from a stray. If no specific breed is given, removes a random breed.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `breed_id` | int | Internal breed ID to remove — omit for a random breed |
| `min_rarity` / `max_rarity` | string | Filter random breed removal by rarity (same values as `add_breed`) |
| `save_as` / `use_saved` | string | Named slots |

### `rename_pooch`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `name` | string | **Required.** New name for the pooch(es) |
| `use_saved` | string | Named slot |

### `modify_breeding_cooldown`

Modifies or sets breeding cooldown. The legacy name `set_breeding_cooldown` still works as an alias.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `amount` | int | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | Random delta in range |
| `exclude_amount` | list[int] | Values to exclude from the random range |
| `roll_once` | bool | Roll once for all targets |
| `mode` | string | `"modify"` (default) or `"set"` (clamped to ≥ 0) |
| `cooldown` | int or `"base"` | Legacy key — sets cooldown directly. `"base"` resets to mutation-adjusted base. Use `amount` + `mode: "set"` instead. |
| `save_as` / `use_saved` | string | Named slots |

### `modify_strength` / `modify_cuteness` / `modify_fluffiness` / `modify_intelligence` / `modify_dexterity` / `modify_fertility` / `modify_aggressiveness` / `modify_constitution`

Modifies one of the eight pooch stats. All support the same parameters as `modify_base_health` / `modify_pooch_age`.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | `"random"` (default), `"all"`, `"random_exclude"`, `"all_exclude"` |
| `count` | int | |
| `filter` | object | Pooch filter |
| `amount` | int | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | Random delta in range |
| `exclude_amount` | list[int] | Values to exclude |
| `roll_once` | bool | Roll once for all targets |
| `mode` | string | `"modify"` (default) or `"set"` |
| `save_as` / `use_saved` | string | Named slots |

### `damn_pooch`

Sends a stray to Hell without any reward. The stray is killed and removed from the stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `save_as` / `use_saved` | string | Named slots — damned pooch ID saved for potential later `revive_pooch` |

### `revive_pooch`

Revives a dead or damned pooch, returning it to life and routing it to a destination.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `destination` | string | `"stray"` (default) — re-adds to the stray pool; `"kennel"` — places in a random owner kennel with free space; `"vendor"` — places in a random vendor's stock |
| `save_as` / `use_saved` | string | Named slots |

### `create_pooch`

Creates a new ownerless pooch and adds it directly to the server's stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `name` | string | Defaults to a generated name |
| `sex` | string | `"male"` or `"female"` — random if omitted |
| `age` | int | Default: `0` |
| `base_health` | int | Default value from constants |
| `strength` / `cuteness` / `fluffiness` / `intelligence` / `dexterity` / `fertility` / `aggressiveness` / `constitution` | int | Default value from constants |
| `breeding_cooldown` | int | Default value from constants |
| `save_as` | string | Save the new pooch's ID into a named slot |

No `destination` parameter — new pooches always go into the stray pool.

### `clone_pooch`

Duplicates an existing stray into the stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector for the source pooch |
| `filter` | object | Pooch filter for source selection |
| `name` / `sex` / `age` / `base_health` / `breeding_cooldown` | various | Override clone attributes |
| `strength` / `cuteness` / `fluffiness` / `intelligence` / `dexterity` / `fertility` / `aggressiveness` / `constitution` | int | Override individual stat attributes on the clone |
| `save_as` | string or list | Save clone and/or source into named slots |

`save_as` list form: `[{ "slot": "...", "target": "clone" \| "source" }]`

### `breed_pooches`

Breeds two strays. The offspring enters the stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `first_pooch_selector` / `second_pooch_selector` | string | Selector for each parent (default: `"random"`) |
| `first_filter` / `second_filter` | object | Pooch filters for each parent |
| `require_unique` | bool | If `true`, ensure the two parents are different pooches (default: `true`) |
| `require_same` | bool | If `true`, both parents are the same pooch (self-breeding) |
| `baby_name` / `baby_age` / `baby_base_health` / `baby_breeding_cooldown` | various | Override offspring attributes |
| `save_as` | string or list | Save participants into named slots |

`save_as` list form: `[{ "slot": "...", "target": "baby" \| "first_parent" \| "second_parent" }]`

### `enter_kennel`

Removes a stray from the pool and places it in a random owner kennel with free space. The stray becomes owned.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector for which stray(s) to place |
| `count` | int | |
| `filter` | object | Pooch filter |
| `save_as` / `use_saved` | string | Named slots |

If no kennel with free space is found, the stray is left as-is.

### `enter_vendor_stock`

Removes a stray from the pool and adds it to a random vendor's stock on the server. The stray becomes owned by the vendor.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `save_as` / `use_saved` | string | Named slots |

If the server has no vendors, the stray is left as-is.

### `start_stray_event`

Chains into another stray event. The sub-event's actions run immediately within the same context, sharing named slots.

| Parameter | Type | Notes |
|-----------|------|-------|
| `event` | string | **Required.** Name of the stray event to trigger |

### `select_pooch`

Resolves a stray from the candidate pool and saves the ID into a named slot. No other side effects. Useful for naming participants before `outcomes` reference them via `stat_weights`.

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | `"random"` (default), `"all"`, `"random_exclude"`, `"all_exclude"` |
| `count` | int | Number to pick or exclude |
| `filter` | object | Pooch filter to narrow the pool |
| `save_as` | string | **Required** for this action to be useful. Saves resolved IDs into a named slot. |
| `use_saved` | string | Use IDs from a named slot instead of resolving via `selector` |

---

## Outcomes

Stray events can have an `outcomes` list alongside (or instead of) top-level `actions`. After the top-level actions run, exactly one outcome is selected and its `actions` execute.

```jsonc
"outcomes": [
    {
        "chance": 0.6,
        "actions": [/* ... */]
    },
    {
        "chance": 0.4,
        "stat_weights": [
            { "stat": "strength", "pooch": "fighter_a", "scale": 0.05 }
        ],
        "actions": [/* ... */]
    }
]
```

### Outcome Parameters

| Field | Type | Notes |
|-------|------|-------|
| `chance` | float (0–1) | Base probability for this outcome |
| `stat_weights` | list | Optional list of stat modifier entries (see below) |
| `actions` | list | Actions executed when this outcome is selected |

### Outcome Selection Rules

Outcomes are split into two groups:

- **Fixed** — has an explicit `chance` and **no** `stat_weights`. The exact probability is reserved and untouched by stat weighting.
- **Dynamic** — has `stat_weights`, or has no `chance` at all (implicit). Dynamic outcomes compete for whatever probability is left after all fixed outcomes are reserved.

For dynamic outcomes:
1. Each outcome's *raw score* = `chance * stat_multiplier` (where `chance` defaults to `1.0` if omitted, and `stat_multiplier` is the product of all stat modifier entries).
2. Raw scores are normalised so the dynamic pool shares exactly `1.0 − sum(fixed chances)` of the total probability.

### `stat_weights` Entries

Each entry computes a multiplier that adjusts an outcome's raw score based on one pooch stat.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `stat` | string | **required** | Stat name: `strength`, `cuteness`, `fluffiness`, `intelligence`, `dexterity`, `fertility`, `aggressiveness`, `constitution`, `base_health`, or `size` |
| `pooch` | string | `"random"` | Named `save_as` slot (e.g. `"fighter_a"`) or `"random"` to pick a random candidate |
| `scale` | float | **required** | Multiplier magnitude per stat point away from `pivot` |
| `pivot` | float | `10.0` | Stat value at which this entry contributes a multiplier of exactly `1.0` |
| `direction` | float | `1.0` | `1.0` = higher stat boosts this outcome; `-1.0` = higher stat hurts it |

**Entry multiplier formula:** `max(0, 1.0 + (stat_value − pivot) × scale × direction)`

**Outcome multiplier:** product of all entry multipliers.

**`size`** maps breed size strings to numeric values: `tiny=4, small=7, average=10, large=13, massive=16`. For mixed-breed pooches the weighted average across breeds is used.

---

## Example Events

### A healthy stray appears

```jsonc
// resources/stray_events/encounters/lucky_stray.jsonc
{
    "name": "Lucky Stray",
    "description": "A remarkably healthy stray appears on the streets.",
    "severity": "MINOR",
    "rarity": "UNCOMMON",
    "actions": [
        {
            "action_type": "create_pooch",
            "target_type": "pooch",
            "parameters": {
                "base_health": 20,
                "age": 0
            }
        }
    ]
}
```

### Street fight between two strays

Outcomes are stat-weighted: a stronger, more aggressive, or larger fighter is more likely to win. The draw outcome has a fixed `chance` that is never affected by stats.

```jsonc
// resources/stray_events/encounters/street_fight.jsonc
{
    "name": "Street Fight",
    "severity": "MAJOR",
    "rarity": "COMMON",
    "filter": { "min_count": 2 },
    "actions": [
        // Name the two fighters via select_pooch (no side effects)
        { "action_type": "select_pooch", "parameters": { "selector": "random", "save_as": "fighter_a" } },
        { "action_type": "select_pooch", "parameters": { "selector": "random", "save_as": "fighter_b" } }
    ],
    "outcomes": [
        {
            "chance": 0.35,
            "stat_weights": [
                { "stat": "strength",       "pooch": "fighter_a", "scale": 0.04, "direction":  1 },
                { "stat": "aggressiveness", "pooch": "fighter_a", "scale": 0.03, "direction":  1 },
                { "stat": "size",           "pooch": "fighter_a", "scale": 0.02, "direction":  1 },
                { "stat": "strength",       "pooch": "fighter_b", "scale": 0.04, "direction": -1 },
                { "stat": "aggressiveness", "pooch": "fighter_b", "scale": 0.03, "direction": -1 }
            ],
            "actions": [
                { "action_type": "modify_pooch_health", "parameters": { "use_saved": "fighter_a", "min_amount": -3, "max_amount": -1 } },
                { "action_type": "modify_pooch_health", "parameters": { "use_saved": "fighter_b", "min_amount": -10, "max_amount": -5 } }
            ]
        },
        {
            "chance": 0.35,
            "stat_weights": [
                { "stat": "strength",       "pooch": "fighter_b", "scale": 0.04, "direction":  1 },
                { "stat": "aggressiveness", "pooch": "fighter_b", "scale": 0.03, "direction":  1 },
                { "stat": "size",           "pooch": "fighter_b", "scale": 0.02, "direction":  1 },
                { "stat": "strength",       "pooch": "fighter_a", "scale": 0.04, "direction": -1 },
                { "stat": "aggressiveness", "pooch": "fighter_a", "scale": 0.03, "direction": -1 }
            ],
            "actions": [
                { "action_type": "modify_pooch_health", "parameters": { "use_saved": "fighter_b", "min_amount": -3, "max_amount": -1 } },
                { "action_type": "modify_pooch_health", "parameters": { "use_saved": "fighter_a", "min_amount": -10, "max_amount": -5 } }
            ]
        },
        {
            "chance": 0.30,
            "actions": [
                { "action_type": "modify_pooch_health", "parameters": { "use_saved": "fighter_a", "min_amount": -6, "max_amount": -3 } },
                { "action_type": "modify_pooch_health", "parameters": { "use_saved": "fighter_b", "min_amount": -6, "max_amount": -3 } }
            ]
        }
    ]
}
```

### A stray wanders into a kennel

```jsonc
// resources/stray_events/misfortune/stray_adoption.jsonc
{
    "name": "Stray Adoption",
    "description": "A wandering stray finds its way into an owner's kennel.",
    "severity": "MINOR",
    "rarity": "UNCOMMON",
    "filter": {
        "min_count": 1
    },
    "actions": [
        {
            "action_type": "enter_kennel",
            "target_type": "pooch",
            "parameters": {
                "selector": "random"
            }
        }
    ]
}
```

---

## Cadence

- **One event per server per day** during the day-change cycle.
- The event is selected by rarity-weighted random sampling from all non-`triggered_only` events whose filter passes for that server.
- If no eligible event exists for a server, no stray event fires that day.
- Stray events run **after** the minimum-stray guarantee (ensuring at least one stray exists before events fire) and **before** vendor restock.
