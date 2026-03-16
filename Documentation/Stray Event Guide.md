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

```json
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

### Advanced Options

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
| `"all_exclude"` | Target every stray **not** matched by the action's `filter`. Useful for "affect all strays that don't have X". |

`"selected"` is not available for stray events (there is no player-driven pre-selection).

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
| `modify_pooch_health` | Modify base health |
| `modify_pooch_age` | Modify age |
| `kill_pooch` | Kill the stray |
| `add_mutation` | Add a mutation |
| `remove_mutation` | Remove a mutation |
| `add_breed` | Add a breed weight |
| `create_pooch` | Create a new stray and add it to the pool |
| `clone_pooch` | Duplicate an existing stray into the pool |
| `rename_pooch` | Rename a stray |
| `set_breeding_cooldown` | Set breeding cooldown |
| `breed_pooches` | Breed two strays; offspring enters the stray pool |
| `enter_kennel` | Move a stray into a random owner kennel with free space |
| `enter_vendor_stock` | Move a stray into a random vendor's stock |
| `start_stray_event` | Trigger another stray event, chaining its actions |

Actions **not** supported in stray events (owner-only):
`modify_money`, `modify_bloodskulls`, `modify_kennel_capacity`, `sell_pooch`, `buy_pooch`, `release_stray`, `receive_stray`, `transfer_pooch`, `start_event`

---

## Action Parameter Reference

Most action parameters mirror the owner event system. Only stray-specific differences are noted.

### `modify_pooch_health` / `modify_pooch_age`

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
| `save_as` / `use_saved` | string | Named slots |

### `add_breed`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `breed` | string | Breed name — omit for a random breed |
| `weight` | float | Breed weight (default: `0.5`) |
| `save_as` / `use_saved` | string | Named slots |

### `rename_pooch`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `name` | string | **Required.** New name for the pooch(es) |
| `use_saved` | string | Named slot |

### `set_breeding_cooldown`

| Parameter | Type | Notes |
|-----------|------|-------|
| `selector` | string | Selector |
| `count` | int | |
| `filter` | object | Pooch filter |
| `cooldown` | int or `"base"` | **Required.** Days to set; `"base"` resets to the mutation-adjusted base cooldown |
| `save_as` / `use_saved` | string | Named slots |

### `create_pooch`

Creates a new ownerless pooch and adds it directly to the server's stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `name` | string | Defaults to a generated name |
| `sex` | string | `"male"` or `"female"` — random if omitted |
| `age` | int | Default: `0` |
| `base_health` | int | Default value from constants |
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
| `save_as` | string or list | Save clone and/or source into named slots |

`save_as` list form: `[{ "slot": "...", "target": "clone" \| "source" }]`

### `breed_pooches`

Breeds two strays. The offspring enters the stray pool.

| Parameter | Type | Notes |
|-----------|------|-------|
| `first_selector` / `second_selector` | string | Selector for each parent (default: `"random"`) |
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

```jsonc
// resources/stray_events/encounters/street_fight.jsonc
{
    "name": "Street Fight",
    "description": "Two strays get into a vicious fight.",
    "severity": "MAJOR",
    "rarity": "COMMON",
    "filter": {
        "min_count": 2
    },
    "actions": [
        {
            "action_type": "modify_pooch_health",
            "target_type": "pooch",
            "parameters": {
                "selector": "random",
                "save_as": "combatant_a",
                "min_amount": -8,
                "max_amount": -3
            }
        },
        {
            "action_type": "modify_pooch_health",
            "target_type": "pooch",
            "parameters": {
                "selector": "random",
                "min_amount": -5,
                "max_amount": -2
            }
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
