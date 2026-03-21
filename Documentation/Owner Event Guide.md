# Owner Event Guide

## Structure

### JSON

Owner events live in `resources/owner_events/**/*.jsonc`. Each event is its own file, placed inside a category subfolder. The category is determined by the folder name, not by any key in the file.

```jsonc
{
    "name": "string",
    "description": "string",
    "flavor_text": "string",
    "severity": "string",
    "rarity": "string",
    "requires_response": "bool",
    "response_timeout": "int",
    "triggered_only": "bool",
    "filter": {},
    "parameters": {},
    "actions": [
        {
            "action_type": "string",
            "target_type": "string",
            "parameters": {}
        }
    ],
    "options": [
        {
            "label": "string",
            "description": "string",
            "default": "bool",
            "visible": "bool",
            "filter": {},
            "parameters": {},
            "actions": [
                {
                    "action_type": "string",
                    "target_type": "string",
                    "parameters": {}
                }
            ],
            "outcomes": [
                {
                    "chance": "float",
                    "message": "string",
                    "actions": [
                        {
                            "action_type": "string",
                            "target_type": "string",
                            "parameters": {}
                        }
                    ]
                }
            ]
        }
    ]
}
```

---

## Event Parameters

### Category

The event category comes from the name of the folder the file is placed in. Folder names are titleized automatically (`dark_rituals` → `Dark Rituals`).

Examples:

- `resources/owner_events/fortune/` → `Fortune`
- `resources/owner_events/misfortune/` → `Misfortune`
- `resources/owner_events/mutation/` → `Mutation`
- `resources/owner_events/supernatural/` → `Supernatural`
- `resources/owner_events/breeding/` → `Breeding`

---

### Event Name

The event name comes from the file's `name` field.

Examples:

- `"Escaped Pooch"`
- `"Vet Bill"`
- `"Strange Mutation"`

---

### Description

The main descriptive text for the event.

---

### Flavor Text

Optional extra flavor for the event.

---

### Severity

How impactful the event is.

Current severity levels:

- `TRIVIAL`
- `MINOR`
- `MODERATE`
- `MAJOR`
- `CRITICAL`
- `CATASTROPHIC`

---

### Rarity

How likely the event is to appear relative to other owner events.

Current rarity levels:

- `COMMON`
- `UNCOMMON`
- `NOVEL`
- `RARE`
- `UNPRECEDENTED`
- `REMARKABLE`
- `EXTRAORDINARY`
- `UNIQUE`

These use relative weights, not direct percentages.

---

### Requires Response

Whether the player must choose an option.

- `true`: the event waits for a response. Top-level `actions` fire immediately when the event triggers. If the event expires without a response, the `default` option is executed.
- `false`: the event resolves immediately. Top-level `actions` fire and the event is archived.

---

### Response Timeout

How long the player has to respond, in seconds.

If the event times out, the option marked `"default": true` is executed automatically.

---

### Triggered Only

If `true`, the event is excluded from normal random owner-event rolls and is only meant to be started explicitly by code or by another event action.

---

### Filter

Eligibility requirements for the event.

If omitted or empty, any owner is eligible.

See **Filtering Guide** below for the full format.

---

### Parameters

A free-form object for specialized or future behavior.

---

### Actions

Top-level event actions. These always fire immediately when the event is triggered, before the player makes any choice.

---

### Options

The list of choices the player can select.

Each option can also have its own `filter`. An option is selectable only if its filter passes for the current owner.

For `requires_response: true` events, exactly one option must be marked `"default": true`. This option executes automatically if the event expires without a response.

---

## Option Parameters

Options are objects inside an event's `options` list.

```jsonc
{
    "label": "string",
    "description": "string",
    "default": false,
    "visible": true,
    "filter": {},
    "parameters": {},
    "actions": [],
    "outcomes": []
}
```

### Label

The button / menu text shown to the player.

### Description

A short explanation of what the option means.

### Default

Whether this is the fallback option that executes when the event expires without a response.

- `true`: this option runs automatically on expiry
- `false` (default): this option does not run on expiry

For `requires_response: true` events, exactly one option must be `"default": true`. The validator enforces this.

### Visible

Whether this option is shown to the player (only relevant for default options).

- `true` (default): the option appears as a choice the player can select
- `false`: the option is hidden and can only execute on expiry (requires `"default": true`)

### Filter

Extra eligibility requirements for selecting this option.

If omitted or empty, the option has no additional restrictions beyond the event itself.

### Actions

Guaranteed actions that happen immediately when this option is selected (or executed on expiry).

### Outcomes

Chance-based branches that happen after the option's guaranteed actions.

Outcomes are split into two groups:

- **Fixed** — has an explicit `chance` and **no** `stat_weights`. The exact probability is reserved and cannot be modified.
- **Dynamic** — has `stat_weights`, or has no `chance` at all (implicit). Dynamic outcomes compete for whatever probability is left after all fixed outcomes reserve their share.

If every outcome is fixed (no `stat_weights` anywhere) they must sum to exactly `1.0`. Fixed-only chances must not exceed `1.0` total.

---

## Outcome Parameters

Outcomes are objects inside an option's `outcomes` list.

```jsonc
{
    "chance": "float",
    "stat_weights": [],
    "message": "string",
    "actions": []
}
```

### Chance

A floating point value between `0.0` and `1.0`.

- For **fixed** outcomes (no `stat_weights`): the exact probability reserved for this outcome.
- For **dynamic** outcomes (has `stat_weights`): the base weight before stat modifiers are applied. Omitting `chance` on a dynamic outcome uses a base weight of `1.0`.

### `stat_weights`

An optional list of stat modifier entries. When present, the outcome's weight is adjusted by the pooches' stats before normalisation.

Each entry:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `stat` | string | **required** | `strength`, `cuteness`, `fluffiness`, `intelligence`, `dexterity`, `fertility`, `aggressiveness`, `constitution`, `base_health`, or `size` |
| `pooch` | string | `"random"` | Named `save_as` slot or `"random"` to pick randomly from affected pooches |
| `scale` | float | **required** | Multiplier magnitude per stat point away from `pivot` |
| `pivot` | float | `10.0` | Stat value at which this entry contributes a multiplier of exactly `1.0` |
| `direction` | float | `1.0` | `1.0` = higher stat boosts this outcome; `-1.0` = higher stat hurts it |

**Entry multiplier:** `max(0, 1.0 + (stat_value − pivot) × scale × direction)`

**Outcome multiplier:** product of all entry multipliers.

The final weight of a dynamic outcome = `chance × multiplier`, normalised so all dynamic outcomes share `1.0 − sum(fixed chances)`.

**`size`** maps breed size to a number: `tiny=4, small=7, average=10, large=13, massive=16` (weighted average for mixed-breed pooches).

To reference specific pooches, write them to named slots with `select_pooch` or `save_as` in top-level/option actions, then use the slot name as the `pooch` value in `stat_weights`.

### `select_pooch` action

Resolves a pooch and saves the ID into a named slot with no other side effects. Useful for naming participants before outcomes reference them via `stat_weights`.

| Parameter | Type | Notes |
|-----------|------|-------|
| `target_type` | string | `"pooch"`, `"owner"`, or `"kennel"` |
| `selector` | string | `"selected"`, `"random"`, `"all"`, `"random_exclude"`, `"all_exclude"` |
| `count` | int | For `"random"`: number to pick |
| `filter` | object | Pooch filter to narrow the pool |
| `save_as` | string | **Required** for this action to be useful |
| `use_saved` | string | Use IDs from a named slot |

### Message

The text shown if this outcome is selected.

### Actions

The actions that happen for this outcome.

---

# Filtering Guide

Owner events and owner-event options both use the same `filter` format.

An empty filter means no restrictions. Example:
```jsonc
"filter": {
    "min_money": 100,
    "max_money": 500,
    "kennels": [
        {
            "min_count": 2,
            "min_pooches": 1
        },
        {
            "min_count": 1,
            "pooches": [
                {
                    "min_count": 1,
                    "min_age": 5,
                    "sex": "female"
                }
            ]
        }
    ],
    "pooches": [
        {
            "min_count": 2,
            "is_alive": true,
            "sex": "male"
        }
    ]
}
```

That example means the owner must:

1. have between 100 and 500 dollars
2. own at least 2 kennels with at least 1 pooch
3. own at least 1 kennel containing at least 1 pooch that is at least 5 years old and female
4. own at least 2 male living pooches anywhere they own them

## General Rules

- If `filter` is omitted or `{}`, no filtering occurs.
- Every entry in `kennels` must independently pass.
- Every entry in `pooches` must independently pass.
- The same object may satisfy multiple filter entries.
- A count-only filter is valid. Example:

```jsonc
"kennels": [
    {
        "max_count": 3
    }
]
```

That means the owner may own at most three kennels, regardless of other kennel attributes.

---

## Owner-Level Filter Fields

These fields live directly inside the root `filter` object:

- `min_money`
- `max_money`
- `exclude_money`
- `min_bloodskulls`
- `max_bloodskulls`
- `exclude_bloodskulls`
- `min_pooches`
- `max_pooches`
- `exclude_pooches`
- `min_kennels`
- `max_kennels`
- `exclude_kennels`
- `kennels`
- `pooches`
- `graveyard_pooches`
- `hell_pooches`

### Owner Counts

- `min_pooches` / `max_pooches` count all pooches owned by the owner, regardless of kennel placement
- `min_kennels` / `max_kennels` count all kennels owned by the owner

### Exclusion Lists

Any numeric range field has a corresponding `exclude_*` list that explicitly disqualifies owners whose value matches any entry in the list.

```jsonc
"filter": {
    "min_pooches": 4,
    "max_pooches": 7,
    "exclude_pooches": [5, 6]
}
```

That matches owners with exactly 4 or 7 pooches, but not 5 or 6.

---

## Kennel Filter Objects

Kennel filter objects live inside `filter.kennels`.

```jsonc
{
    "min_count": 1,
    "max_count": 3,
    "min_capacity": 2,
    "max_capacity": 8,
    "exclude_capacity": [3, 7],
    "min_pooches": 1,
    "max_pooches": 5,
    "exclude_pooches": [2],
    "pooches": []
}
```

### Kennel Filter Fields

- `min_count`
- `max_count`
- `description`
- `min_capacity`
- `max_capacity`
- `exclude_capacity`
- `min_pooches`
- `max_pooches`
- `exclude_pooches`
- `pooches`

### Kennel Semantics

- `min_count` / `max_count` apply to the number of kennels matching that kennel filter
- `min_pooches` / `max_pooches` apply to the number of pooches currently in an individual kennel
- `max_pooches` can be set to `"capacity - [X]"` to set the max relative to the kennel's capacity, like `"capacity - 1"`
- `exclude_capacity` / `exclude_pooches` are integer lists that exclude kennels whose capacity or pooch count equals any value in the list
- nested `pooches` filters apply only to pooches inside that kennel

---

## Pooch Filter Objects

Pooch filter objects live either:

- inside the top-level `filter.pooches`
- or inside a kennel filter's `pooches`

```jsonc
{
    "min_count": 1,
    "max_count": 3,
    "min_age": 5,
    "max_age": 10,
    "exclude_age": [7],
    "sex": "female",
    "min_health": 3,
    "max_health": 8,
    "exclude_health": [5],
    "is_virgin": true,
    "is_alive": true,
    "min_breeding_cooldown": 0,
    "max_breeding_cooldown": 2,
    "exclude_breeding_cooldown": [1],
    "has_any_breed": ["Husky", "Poodle"],
    "has_all_breeds": ["Wolfhound"],
    "exclude_breeds": ["Chihuahua"],
    "has_any_mutation": ["heterochromia"],
    "has_all_mutations": ["gigantism"],
    "exclude_mutations": ["dwarfism"],
    "location": "kennel"
}
```

### Pooch Filter Fields

- `min_count`
- `max_count`
- `description`
- `min_age`
- `max_age`
- `exclude_age`
- `sex`
- `min_health`
- `max_health`
- `exclude_health`
- `is_virgin`
- `is_alive`
- `min_breeding_cooldown`
- `max_breeding_cooldown`
- `exclude_breeding_cooldown`
- `has_any_breed`
- `has_all_breeds`
- `exclude_breeds`
- `has_any_mutation`
- `has_all_mutations`
- `exclude_mutations`
- `location`

### Pooch Field Notes

- `health` uses the pooch's effective current health, including mutation contributions (matches `get_pooch_health`)
- breed and mutation references are always by **name**, never by internal database ID
- `location` can be:
  - `"kennel"`: the pooch must currently be in a kennel
  - `"graveyard"`: the pooch is dead and buried
  - `"hell"`: the pooch has been damned
  - `"town"`: the pooch is a stray in a server
  - `"all"` / `"any"`: no location restriction

For top-level `filter.pooches`, matching is across all pooches the owner owns.
For nested kennel `pooches`, matching is only against pooches inside that kennel.

### `graveyard_pooches` and `hell_pooches`

`graveyard_pooches` and `hell_pooches` are pooch filter spec lists on the **owner-level filter** (not inside `kennels`). They work identically to `pooches` but target the owner's dead or condemned pooches respectively.

```jsonc
"filter": {
    "graveyard_pooches": [{ "min_count": 1 }],
    "hell_pooches": [{ "min_count": 1, "has_any_mutation": ["Mild Possession"] }]
}
```

- Each entry in the list is a pooch filter spec that must independently pass.
- `location` is not meaningful inside these specs (it's implied by the pool).
- Useful for events that require a dead or damned pooch to exist before triggering (e.g. revival events, infernal bargains).

---

## Action Targeting Filters

Event actions can also include `parameters.filter` to narrow which targets are affected.

This depends on `target_type`.

If the action targets `"selected"`, the filter is ignored and the already-selected contextual target is used.

If the action targets `"random"`, the filter narrows the random pool.

If the `selector` is `"all"`, the filter narrows which objects are affected.

### Pooch Action Filters

Valid for `target_type: "pooch"` with any `selector` value.

Example:

```jsonc
{
    "action_type": "set_breeding_cooldown",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "filter": {
            "location": "kennel",
            "min_breeding_cooldown": 1
        },
        "cooldown": 0
    }
}
```

That picks a random owned pooch matching the filter.

Pooch action filters use the same pooch attribute fields as normal pooch filters, except they do **not** use `min_count` / `max_count` because they describe one selection pool, not a requirement list.

### Kennel Action Filters

Valid for `target_type: "kennel"` with any `selector` value.

Example:

```jsonc
{
    "action_type": "modify_kennel_capacity",
    "target_type": "kennel",
    "parameters": {
        "selector": "all",
        "filter": {
            "max_capacity": 5,
            "min_pooches": 1
        },
        "amount": 2
    }
}
```

Kennel action filters use kennel attribute fields like:

- `min_capacity`
- `max_capacity`
- `min_pooches`
- `max_pooches`
- `pooches` (nested pooch filters)

They do **not** use `min_count` / `max_count` because action targeting is already selecting from a set of kennel objects.

### Owner Actions

`target_type: "owner"` does not use `parameters.filter`.

---

## About Selectors

Dynamic runtime entities such as pooches and kennels should never be referenced by literal IDs in static event JSON.

Instead, `target_type: "pooch"` and `target_type: "kennel"` actions use a `selector` parameter:

- `"random"` (default): choose one random matching target at action execution time
- `"selected"`: use the event's pre-selected contextual target (resolved once at trigger time)
- `"all"`: apply the action to every matching target
- `"random_exclude"`: apply the action to all matching targets **except** a randomly chosen subset
- `"all_exclude"`: apply the action to every target **not** matched by the filter (inverse of `"all"`)

`"random"` is the default if `selector` is omitted.

`"selected"` is especially useful for events that need to refer to the same target across option branches and outcomes.

`"all_exclude"` inverts the filter — it targets every entity the owner has that does *not* match `filter`. If no filter is specified, `"all_exclude"` targets no entities (the complement of "all" with no exclusions is empty).

### `count` parameter

The `count` parameter controls how many entities the selector picks. It is available alongside `selector` on pooch and kennel actions.

- **With `"random"`**: picks exactly `count` random entities. If fewer than `count` matching entities exist, all of them are used.
- **With `"random_exclude"`**: randomly excludes exactly `count` entities from the affected set. If `count` is not set, or is ≥ the total number of matching entities, the action affects nobody.

```jsonc
// Pick 3 random pooches
{
    "action_type": "modify_pooch_health",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "count": 3,
        "amount": -1
    }
}

// Affect all pooches except 2 randomly spared ones
{
    "action_type": "modify_pooch_health",
    "target_type": "pooch",
    "parameters": {
        "selector": "random_exclude",
        "count": 2,
        "amount": -5
    }
}
```

---

## Filtering Example

The following would live at `resources/owner_events/misfortune/escaped_pooch.jsonc`:

```jsonc
{
    "name": "Escaped Pooch",
    "description": "One of your pooches has escaped from the kennel!",
    "severity": "MAJOR",
    "rarity": "UNCOMMON",
    "requires_response": true,
    "response_timeout": 3600,
    "filter": {
        "pooches": [
            {
                "min_count": 1,
                "is_alive": true
            }
        ]
    },
    "options": [
        {
            "label": "Hire a search party",
            "description": "Pay professionals to look for the pooch.",
            "filter": {
                "min_money": 100
            },
            "actions": [
                {
                    "action_type": "modify_money",
                    "target_type": "owner",
                    "parameters": {
                        "amount": -100
                    }
                }
            ],
            "outcomes": [
                {
                    "chance": 0.9,
                    "message": "The search party finds your pooch."
                },
                {
                    "chance": 0.1,
                    "message": "The pooch is never found.",
                    "actions": [
                        {
                            "action_type": "kill_pooch",
                            "target_type": "pooch",
                            "parameters": {
                                "selector": "selected"
                            }
                        }
                    ]
                }
            ]
        },
        {
            "label": "Give up",
            "description": "Accept that they're gone.",
            "default": true,
            "visible": true,
            "actions": [
                {
                    "action_type": "kill_pooch",
                    "target_type": "pooch",
                    "parameters": {
                        "selector": "selected"
                    }
                }
            ]
        }
    ]
}
```

---

# Action Reference

Actions are structured as:

```jsonc
{
    "action_type": "string",
    "target_type": "string",
    "repeat": 1,
    "parameters": {}
}
```

### `repeat`

An optional integer column (default: `1`) that controls how many times in a row the action is executed. Each repetition is fully independent — random amounts are re-rolled, random targets are re-selected, etc.

```jsonc
// Apply a -5 health hit to a random pooch 3 times (could hit the same pooch multiple times)
{
    "action_type": "modify_pooch_health",
    "target_type": "pooch",
    "repeat": 3,
    "parameters": {
        "selector": "random",
        "amount": -5
    }
}
```

### Supported Action Types

| Action | Target Types | Notes |
|--------|-------------|-------|
| `modify_money` | `owner` | Adjusts the owner's dollars |
| `modify_bloodskulls` | `owner` | Adjusts the owner's bloodskulls |
| `create_pooch` | `owner`, `kennel` | Creates a new pooch for the owner |
| `clone_pooch` | `pooch`, `kennel`, `owner` | Duplicates an existing pooch |
| `conjure_pooch` | `owner` | Conjures a pooch via the ritual without charging bloodskulls |
| `start_event` | `owner` | Triggers another owner event |
| `start_stray_event` | `owner` | Triggers a stray event on one of the owner's servers |
| `modify_base_health` | `pooch`, `kennel`, `owner` | Modifies base health (alias: `modify_pooch_health`) |
| `modify_pooch_age` | `pooch`, `kennel`, `owner` | Modifies age |
| `modify_strength` | `pooch`, `kennel`, `owner` | Modifies strength stat |
| `modify_cuteness` | `pooch`, `kennel`, `owner` | Modifies cuteness stat |
| `modify_fluffiness` | `pooch`, `kennel`, `owner` | Modifies fluffiness stat |
| `modify_intelligence` | `pooch`, `kennel`, `owner` | Modifies intelligence stat |
| `modify_dexterity` | `pooch`, `kennel`, `owner` | Modifies dexterity stat |
| `modify_fertility` | `pooch`, `kennel`, `owner` | Modifies fertility stat |
| `modify_aggressiveness` | `pooch`, `kennel`, `owner` | Modifies aggressiveness stat |
| `modify_constitution` | `pooch`, `kennel`, `owner` | Modifies constitution stat |
| `kill_pooch` | `pooch`, `kennel`, `owner` | Kills the pooch(es) |
| `damn_pooch` | `pooch`, `kennel`, `owner` | Sends a pooch to Hell without reward |
| `revive_pooch` | `pooch`, `kennel`, `owner` | Revives a dead or damned pooch and routes it to a destination |
| `sacrifice_pooch` | `pooch`, `kennel`, `owner` | Sacrifices a pooch to Hell, granting bloodskulls |
| `add_mutation` | `pooch`, `kennel`, `owner` | Adds a mutation |
| `remove_mutation` | `pooch`, `kennel`, `owner` | Removes a mutation |
| `add_breed` | `pooch`, `kennel`, `owner` | Adds a breed weight |
| `remove_breed` | `pooch`, `kennel`, `owner` | Removes a breed |
| `transfer_pooch` | `pooch`, `kennel`, `owner` | Transfers to another owner or vendor |
| `rename_pooch` | `pooch`, `kennel`, `owner` | Renames the pooch |
| `modify_breeding_cooldown` | `pooch`, `kennel`, `owner` | Modifies or sets breeding cooldown (alias: `set_breeding_cooldown`) |
| `modify_kennel_capacity` | `kennel`, `owner` | Adjusts the kennel's pooch limit |
| `breed_pooches` | `owner`, `kennel` | Breeds two of the owner's pooches together |
| `sell_pooch` | `pooch`, `kennel`, `owner` | Sells a pooch, crediting the owner |
| `buy_pooch` | `owner`, `kennel` | Buys a pooch from a vendor |
| `release_stray` | `pooch`, `kennel`, `owner` | Releases a pooch into the stray pool for the owner's server |
| `receive_stray` | `owner`, `kennel` | Claims a random stray pooch from the owner's server |

### Supported Target Types

- `owner`
- `pooch`
- `kennel`

For `pooch` and `kennel` targets, use `parameters.selector` to control which entities are affected:

- `"random"` (default) — one random matching entity
- `"selected"` — the event's pre-selected contextual entity
- `"all"` — every matching entity owned by the player
- `"random_exclude"` — all matching entities except a randomly chosen subset (use with `count`)
- `"all_exclude"` — every entity **not** matched by the filter (inverse of `"all"`)

When `target_type` is `"kennel"` on a **pooch action** (e.g. `kill_pooch`, `modify_pooch_health`), the action applies to pooches *inside* the targeted kennel(s) rather than to the kennel itself. An optional `pooch_filter` parameter can narrow which pooches inside the kennel are affected. Use `pooch_selector` and `pooch_count` to further control which pooches within each resolved kennel are targeted — for example, `pooch_selector: "random_exclude", pooch_count: 1` affects all pooches except one randomly spared survivor.

When `target_type` is `"owner"` on a **pooch action**, the action applies to *all pooches* the owner has, optionally narrowed by a `filter` (pooch filter). When used on a **kennel action**, it applies to all kennels the owner has, optionally narrowed by a `filter` (kennel filter). No `selector` is needed or accepted in either case.

Static event JSON should reference stable content by name and dynamic runtime entities by selector strings.

---

### Carry-Forward: Named Slots (`save_as` / `use_saved`)

Actions execute sequentially in `action_order`. When one action needs to operate on the *same entity* that a previous action resolved, use named slots to carry the resolved IDs forward.

#### `save_as`

After an action resolves its targets, write the IDs into `context.extra_data` under this key.

For most pooch and kennel actions, `save_as` is a plain **string** (the slot name):

- Pooch actions write `{ "pooch_ids": [5, 12, ...] }`
- Kennel actions write `{ "kennel_ids": [3, ...] }`

For `create_pooch`, `save_as` is also a plain string and saves the newly created pooch's ID.

For `clone_pooch` and `breed_pooches`, `save_as` supports an extended form because there are multiple participants to save. It can be either:

- A plain **string** — saves the default participant (clone / baby) into that slot.
- A **list** of `{ "slot": "...", "target": "..." }` objects — each entry saves a specific participant independently.

See the parameter tables for `clone_pooch` and `breed_pooches` for the valid `target` values.

#### `save_kennel` (bool, pooch actions only)

When `save_as` is present on a pooch action, also look up each resolved pooch's kennel and include it in the slot:

```jsonc
{ "pooch_ids": [5], "kennel_ids": [2] }
```

If a pooch has no kennel, `kennel_ids` will be `[]` — any follow-up action targeting that slot is a no-op. Use `filter: { "location": "kennel" }` on the pooch action if you need to guarantee a kennel exists.

#### `use_saved` (string)

Instead of resolving targets via `selector`/`filter`, pull IDs directly from the named slot. Cannot be used together with `selector`. The action type determines which key is read (`pooch_ids` or `kennel_ids`).

#### Example — fire spreads to the kennel

```jsonc
// Action 1: kill a random pooch in a kennel; save which kennel it was in
{
    "action_type": "kill_pooch",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "filter": { "location": "kennel" },
        "save_as": "fire_victim",
        "save_kennel": true
    }
},
// Action 2: damage all pooches in that same kennel
{
    "action_type": "modify_pooch_health",
    "target_type": "kennel",
    "parameters": {
        "use_saved": "fire_victim",
        "min_amount": -2,
        "max_amount": -1
    }
}
```

Slots persist for the lifetime of the event, and you can use them between phases (for instance, using `"save_as": "pooch"` in the event-level action list, then using `"use_saved": "pooch"` in an outcome-level action list).

**Named slots are always forwarded to follow-up events triggered by `start_event`.** The mechanism differs by `requires_response`:

- **Instant follow-up events** (`requires_response: false`) run inline within the same context object — all slots are shared bidirectionally.
- **Response-required follow-up events** (`requires_response: true`) run as independent active events (separate DB record, own expiry timer). All named slots from the triggering event are copied into the new event's context at creation time, so `use_saved` works in the follow-up. Slots written *by* the follow-up are not visible back in the original event.

Internal runtime keys (`candidate_pooch_ids`, `candidate_kennel_ids`, `suppressed_option_ids`, and any key starting with `_`) are never forwarded.

---

### Action Parameter Reference

#### `modify_money` / `modify_bloodskulls`

```jsonc
{
    "action_type": "modify_money",
    "target_type": "owner",
    "parameters": {
        "amount": -50
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `amount` | int | one of | Fixed delta (can be negative); or an absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | one of | Random delta in range; or random absolute value when `mode` is `"set"` |
| `exclude_amount` | list[int] | no | Values to exclude from the random range — only valid with `min_amount`/`max_amount`. If all values are excluded, falls back to `min_amount`. |
| `roll_once` | bool | no | If true, roll the random amount once and apply to all targets |
| `mode` | string | no | `"modify"` (default) — add/subtract the amount; `"set"` — set the value to exactly `amount` |

```jsonc
// Set the owner's money to 0 (wipe them out)
{
    "action_type": "modify_money",
    "target_type": "owner",
    "parameters": {
        "amount": 0,
        "mode": "set"
    }
}
```

---

#### `modify_base_health` / `modify_pooch_age`

> `modify_pooch_health` is a supported alias for `modify_base_health`.

```jsonc
{
    "action_type": "modify_pooch_health",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "filter": { "min_health": 10 },
        "min_amount": -5,
        "max_amount": -1,
        "roll_once": false
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` — not used when `target_type` is `"owner"` or `use_saved` is set |
| `count` | int | no | With `"random"`: number of pooches to pick. With `"random_exclude"`: number to exclude. |
| `filter` | object | no | Pooch filter (`pooch`/`owner`), or kennel filter (`kennel`) |
| `pooch_filter` | object | no | Pooch filter when `target_type` is `"kennel"` |
| `pooch_selector` | string | no | When `target_type` is `"kennel"`: how to pick pooches within each kennel — `"random"`, `"random_exclude"`, or `"all"` (default) |
| `pooch_count` | int | no | When `target_type` is `"kennel"`: with `"random"`: number of pooches per kennel to pick; with `"random_exclude"`: number per kennel to spare |
| `amount` | int | one of | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | one of | Random delta in range; or random absolute value when `mode` is `"set"` |
| `exclude_amount` | list[int] | no | Values to exclude from the random range — only valid with `min_amount`/`max_amount`. Falls back to `min_amount` if all values are excluded. |
| `roll_once` | bool | no | Roll once for all targets instead of per-target |
| `mode` | string | no | `"modify"` (default) — add/subtract the amount; `"set"` — set the stat to exactly `amount` |
| `save_as` | string | no | Save resolved target IDs into a named slot for later actions |
| `save_kennel` | bool | no | Also save kennel IDs of resolved pooches into the slot (requires `save_as`) |
| `use_saved` | string | no | Use IDs from a named slot instead of resolving via `selector` (cannot combine with `selector`) |

```jsonc
// Kill all pooches in a random kennel except one randomly spared survivor
{
    "action_type": "kill_pooch",
    "target_type": "kennel",
    "parameters": {
        "selector": "random",
        "pooch_selector": "random_exclude",
        "pooch_count": 1
    }
}

// Set all pooches' health to exactly 1
{
    "action_type": "modify_pooch_health",
    "target_type": "owner",
    "parameters": {
        "amount": 1,
        "mode": "set"
    }
}
```

---

#### `modify_strength` / `modify_cuteness` / `modify_fluffiness` / `modify_intelligence` / `modify_dexterity` / `modify_fertility` / `modify_aggressiveness` / `modify_constitution`

Modifies one of the eight pooch stats. All support the same parameters as `modify_base_health`.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | |
| `filter` / `pooch_filter` | object | no | |
| `amount` | int | one of | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | one of | Random delta in range |
| `exclude_amount` | list[int] | no | |
| `roll_once` | bool | no | Roll once for all targets |
| `mode` | string | no | `"modify"` (default) or `"set"` |
| `save_as` / `use_saved` | string | no | Named slots |

---

#### `damn_pooch`

Sends a pooch to Hell without any reward (unlike `sacrifice_pooch`). The pooch is killed and removed from its current location (kennel, stray pool, or graveyard) before being placed in Hell.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | |
| `filter` / `pooch_filter` | object | no | |
| `save_as` / `use_saved` | string | no | Named slots — the damned pooch's ID is saved for later use (e.g. `revive_pooch`) |

---

#### `revive_pooch`

Revives a dead or damned pooch, setting it back to alive, removing it from the graveyard or Hell, and routing it to a destination.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | |
| `filter` / `pooch_filter` | object | no | |
| `destination` | string | no | Where to deliver the revived pooch — `"kennel"` (default), `"town"`, `"hell"`, `"graveyard"` |
| `save_as` / `use_saved` | string | no | Named slots |

---

#### `sacrifice_pooch`

Sacrifices a pooch to Hell. The owner receives bloodskulls equal to the pooch's bloodskull value (optionally multiplied), plus 1 bone. The pooch is killed and damned.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | |
| `filter` / `pooch_filter` | object | no | |
| `value_multiplier` | float | no | Multiply bloodskulls received by this factor (default: `1.0`) |
| `save_as` / `use_saved` | string | no | Named slots |

---

#### `conjure_pooch`

Creates a pooch via the conjure ritual without charging bloodskulls. Use separate `modify_bloodskulls` actions to handle any cost. Adds the Mark of the Beast mutation to the conjured pooch automatically.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `num_rolls` | int | no | Number of candidate pooches to generate; the best one by bloodskull value is kept (default: `1`) |
| `destination` | string | no | Where to deliver the conjured pooch — same values as `create_pooch` (default: `"kennel"`) |
| `save_as` | string | no | Save the conjured pooch's ID into a named slot |

---

#### `kill_pooch`

```jsonc
{
    "action_type": "kill_pooch",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "filter": { "location": "kennel" }
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number of pooches to pick (`"random"`) or exclude (`"random_exclude"`) |
| `filter` | object | no | Pooch filter (`pooch`/`owner`), or kennel filter (`kennel`) |
| `pooch_filter` | object | no | Pooch filter when `target_type` is `"kennel"` |
| `save_as` | string | no | Save resolved pooch IDs (and optionally kennel) into a named slot |
| `save_kennel` | bool | no | Also save kennel IDs of resolved pooches (requires `save_as`) |
| `use_saved` | string | no | Use IDs from a named slot instead of `selector` |

---

#### `add_mutation` / `remove_mutation`

```jsonc
{
    "action_type": "add_mutation",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "mutation": "Iron Stomach"
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick (`"random"`) or exclude (`"random_exclude"`) |
| `filter` / `pooch_filter` | object | no | Filters |
| `mutation` | string | no | Mutation name — omit for a random mutation |
| `mutation_id` | int | no | Internal mutation ID — omit for a random mutation (prefer `mutation` over this) |
| `min_rarity` / `max_rarity` | string | no | Filter random mutation pool by rarity — values: `common`, `uncommon`, `novel`, `rare`, `unprecedented`, `remarkable`, `extraordinary`, `unique` |
| `min_health_impact` / `max_health_impact` | string | no | Filter random mutation pool by health impact — values: `instant_death`, `fatal`, `brutal`, `severe`, `unhealthy`, `harmful`, `neutral`, `helpful`, `healthy`, `great`, `fantastic`, `brilliant`, `immortality` |
| `save_as` / `use_saved` | string | no | Named slots |

Rarity and health_impact filters only apply when no specific `mutation` / `mutation_id` is given (i.e. when selecting randomly).

---

#### `add_breed`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick or exclude |
| `filter` / `pooch_filter` | object | no | |
| `breed` | string | no | Breed name — omit for a random breed |
| `weight` | float | no | Breed weight, must be > 0 (default: `0.5`) |
| `min_rarity` / `max_rarity` | string | no | Filter random breed pool by rarity — values: `common`, `uncommon`, `novel`, `rare`, `unprecedented`, `remarkable`, `extraordinary`, `unique` |
| `save_as` / `use_saved` | string | no | Named slots |

Rarity filters only apply when no specific `breed` is given.

---

#### `remove_breed`

Removes a breed from a pooch. If no breed is specified, removes a random breed from the pooch.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick or exclude |
| `filter` / `pooch_filter` | object | no | |
| `breed_id` | int | no | Internal breed ID to remove — omit for a random breed |
| `min_rarity` / `max_rarity` | string | no | Filter random breed removal by rarity (same values as `add_breed`) |
| `save_as` / `use_saved` | string | no | Named slots |

---

#### `transfer_pooch`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick or exclude |
| `filter` / `pooch_filter` | object | no | |
| `new_owner_discord_id` | int | one of | Transfer to this owner |
| `vendor_id` | int | one of | Transfer to this vendor |

---

#### `create_pooch`

Creates a new pooch and optionally delivers it to a destination.

```jsonc
{
    "action_type": "create_pooch",
    "target_type": "owner",
    "parameters": {
        "sex": "female",
        "age": 0,
        "base_health": 100,
        "destination": "kennel",
        "save_as": "new_pooch"
    }
}
```

**Supported target types:** `owner`, `kennel`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `name` | string | no | Defaults to a generated name |
| `sex` | string | no | `"male"` or `"female"` — random if omitted |
| `age` | int | no | Default: 0 |
| `base_health` | int | no | Default value from constants |
| `strength` / `cuteness` / `fluffiness` / `intelligence` / `dexterity` / `fertility` / `aggressiveness` / `constitution` | int | no | Default value from constants |
| `breeding_cooldown` | int | no | Default value from constants |
| `destination` | string | no | Where to deliver the pooch (see below) — default: `"kennel"`. Ignored when `target_type` is `"kennel"`. |
| `selector` | string | yes (kennel) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` — selects which kennel to deliver to. Multi-kennel selectors use the first resolved kennel. |
| `filter` | object | no | Kennel filter — only used when `target_type` is `"kennel"` |
| `save_as` | string | no | Save the new pooch's ID into a named slot for use by later actions |

When `target_type` is `"kennel"`, the pooch is placed directly into the resolved kennel. If the kennel is full, the pooch is left unhoused in town.

##### `destination` values (owner target only)

| Value | Effect |
|-------|--------|
| `"kennel"` (default) | Place in the first kennel the owner has with free space. Falls back to `"town"` (stray) if all kennels are full. The result message names the kennel. |
| `"graveyard"` | Send directly to the owner's graveyard. |
| `"hell"` | Damn the pooch to Hell. |
| `"town"` | Release the pooch as a stray — it becomes unowned and joins the server's stray pool. |

---

#### `clone_pooch`

Duplicates an existing pooch, inheriting its name, stats, breeds, and mutations. Any field can be overridden in parameters. Uses the same target/selector system as other pooch actions to select the source.

```jsonc
{
    "action_type": "clone_pooch",
    "target_type": "pooch",
    "parameters": {
        "selector": "selected",
        "destination": "kennel",
        "save_as": "the_clone"
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (pooch/kennel target; also accepted with owner target) | `"random"`, `"selected"`, or `"all"` (picks first) — selects the source pooch |
| `filter` / `pooch_filter` | object | no | Filters for source pooch selection |
| `name` | string | no | Override — defaults to source's name |
| `sex` | string | no | Override — defaults to source's sex |
| `age` | int | no | Override — defaults to source's age |
| `base_health` | int | no | Override — defaults to source's base health |
| `strength` / `cuteness` / `fluffiness` / `intelligence` / `dexterity` / `fertility` / `aggressiveness` / `constitution` | int | no | Override individual stat — defaults to source's value |
| `breeding_cooldown` | int | no | Override — defaults to source's breeding cooldown |
| `destination` | string | no | Same values as `create_pooch` — default: `"kennel"` |
| `save_as` | string or list | no | Save clone and/or source into named slots (see below) |

The clone always starts as a virgin with `alive = true`, regardless of the source's state.

When `target_type` is `"owner"`, a `selector` and optional `filter` must be provided to choose which of the owner's pooches to clone (unlike other owner-target actions that affect all pooches, `clone_pooch` needs to identify a single source).

##### `save_as` for `clone_pooch`

`save_as` can be a plain string (saves the clone) or a list of `{ "slot": "...", "target": "..." }` objects to save multiple participants independently.

| `target` | What is saved |
|----------|---------------|
| `"clone"` (default) | The newly created clone |
| `"source"` | The original pooch that was cloned |

Examples:

```jsonc
// Plain string — saves the clone
"save_as": "the_clone"

// List form — save both
"save_as": [
    { "slot": "the_clone", "target": "clone" },
    { "slot": "the_original", "target": "source" }
]
```

---

#### `modify_kennel_capacity`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number of kennels to pick or exclude |
| `filter` | object | no | Kennel filter (`kennel`/`owner`) |
| `amount` | int | one of | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | one of | Random delta in range; or random absolute value when `mode` is `"set"` |
| `exclude_amount` | list[int] | no | Values to exclude from the random range — only valid with `min_amount`/`max_amount`. Falls back to `min_amount` if all values are excluded. |
| `roll_once` | bool | no | Roll once for all kennels |
| `mode` | string | no | `"modify"` (default) — add/subtract the amount; `"set"` — set the capacity to exactly `amount` |
| `save_as` | string | no | Save resolved kennel IDs into a named slot |
| `use_saved` | string | no | Use kennel IDs from a named slot instead of `selector` |

---

#### `rename_pooch`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick or exclude |
| `filter` / `pooch_filter` | object | no | |
| `name` | string | yes | New name for the pooch |

---

#### `modify_breeding_cooldown`

Modifies or sets breeding cooldown. The legacy name `set_breeding_cooldown` still works as an alias.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick or exclude |
| `filter` / `pooch_filter` | object | no | |
| `amount` | int | one of | Fixed delta; or absolute value when `mode` is `"set"` |
| `min_amount` / `max_amount` | int | one of | Random delta in range |
| `exclude_amount` | list[int] | no | Values to exclude from the random range |
| `roll_once` | bool | no | Roll once for all targets |
| `mode` | string | no | `"modify"` (default) — add/subtract the amount; `"set"` — set to exactly `amount` (clamped to ≥ 0) |
| `cooldown` | int or `"base"` | legacy | Legacy key from `set_breeding_cooldown` — sets cooldown to this value. `"base"` resets to the mutation-adjusted base. Use `amount` + `mode: "set"` instead. |
| `save_as` / `use_saved` | string | no | Named slots |

---

#### `start_event`

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `event` | string | one of | Event name to trigger |
| `random_event` | bool | one of | If true, trigger a random eligible event instead |

Named slots from the current event are always forwarded to the triggered event (see Named Slots section for details on what is and isn't forwarded).

---

#### `start_stray_event`

Triggers a stray event on one of the owner's servers (chosen randomly). The stray event runs immediately and its results are merged into the current owner event result. Named slots are **not** shared between the owner event and the stray event (they use separate contexts).

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `event` | string | yes | Name of the stray event to trigger |

---

#### `breed_pooches`

Selects two of the owner's pooches and breeds them. Calls the same breeding logic as manual breeding, so the pooches must be opposite sexes — use `first_filter` / `second_filter` to ensure this.

**Supported target types:** `owner`, `kennel`

```jsonc
{
    "action_type": "breed_pooches",
    "target_type": "owner",
    "parameters": {
        "first_pooch_selector": "random",
        "first_filter": { "sex": "male" },
        "second_pooch_selector": "random",
        "second_filter": { "sex": "female" },
        "baby_base_health": 10
    }
}
```

When `target_type` is `"kennel"`, both parent pools are restricted to pooches within the first resolved kennel. The `selector` / `filter` parameters select which kennel. Multi-kennel selectors (`all`, `all_exclude`, `random_exclude`) use the first kennel in the resolved list. This mirrors how manual breeding works — parents must be in the same kennel.

```jsonc
{
    "action_type": "breed_pooches",
    "target_type": "kennel",
    "parameters": {
        "selector": "selected",
        "first_pooch_selector": "random",
        "first_filter": { "sex": "male" },
        "second_pooch_selector": "random",
        "second_filter": { "sex": "female" }
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (kennel) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` — selects which kennel to restrict breeding to. Multi-kennel selectors use the first resolved kennel. |
| `filter` | object | no | Kennel filter — only used when `target_type` is `"kennel"` |
| `first_pooch_selector` | string | no | `"random"` (default), `"selected"`, `"all"`, or `"all_exclude"` (picks one from the resolved pool) — selects the first parent |
| `first_filter` | object | no | Pooch filter applied to the first parent selection |
| `second_pooch_selector` | string | no | Same values as `first_pooch_selector`, applied to the second parent |
| `second_filter` | object | no | Pooch filter applied to the second parent selection |
| `require_unique` | bool | no | If `true`, the second pooch is picked from the pool with the first pooch excluded — if no second distinct pooch can be found, breeding is skipped (default: `true`) |
| `require_same` | bool | no | If `true`, force the second parent to be the same pooch as the first (ignores `second_pooch_selector`) |
| `baby_name` | string | no | Override the generated baby name |
| `baby_sex` | string | no | `"male"` or `"female"` — random if omitted |
| `baby_age` | int | no | Override the baby's starting age |
| `baby_base_health` | int | no | Override the baby's base health |
| `baby_breeding_cooldown` | int | no | Override the baby's initial breeding cooldown |
| `save_as` | string or list | no | Save one or more participants into named slots (see below) |

This action bypasses the usual restrictions for which pooches can breed (i.e. different sexes, no breeding cooldown, etc.). Use filters to add the desired restrictions. `require_unique` guarantees distinct parents by removing the first selected pooch from the pool before picking the second — if no second distinct pooch is found after exclusion, the entire action is skipped.

##### `save_as` for `breed_pooches`

`save_as` can be a plain string (saves the baby/babies) or a list of `{ "slot": "...", "target": "..." }` objects to save multiple participants independently.

| `target` | What is saved |
|----------|---------------|
| `"baby"` (default) | The baby or babies that were born |
| `"first_parent"` | The first parent pooch |
| `"second_parent"` | The second parent pooch |

Examples:

```jsonc
// Plain string — saves the baby IDs
"save_as": "the_baby"

// List form — save all three participants
"save_as": [
    { "slot": "the_baby", "target": "baby" },
    { "slot": "the_father", "target": "first_parent" },
    { "slot": "the_mother", "target": "second_parent" }
]
```

---

#### `sell_pooch`

Sells one or more of the owner's pooches, crediting the owner with the sale price. The pooch is removed from the owner's collection.

```jsonc
{
    "action_type": "sell_pooch",
    "target_type": "pooch",
    "parameters": {
        "selector": "random",
        "filter": { "min_age": 5 },
        "value_multiplier": 1.5
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `selector` | string | yes (except `owner`) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` |
| `count` | int | no | Number to pick (`"random"`) or exclude (`"random_exclude"`) |
| `filter` / `pooch_filter` | object | no | Filters for source pooch selection |
| `use_saved` | string | no | Use IDs from a named slot instead of `selector` |
| `vendor_id` | int | no | Sell to this specific vendor (credits the vendor's stock) |
| `vendor_selector` | string | no | `"random"` — pick a random vendor from the owner's servers to sell to |
| `value_multiplier` | float | no | Multiply the pooch's sale price by this factor (default: `1.0`) |

If neither `vendor_id` nor `vendor_selector` is provided, the pooch is sold for its base price with no vendor involved.

---

#### `buy_pooch`

Buys a pooch from a vendor and delivers it to the owner.

**Supported target types:** `owner`, `kennel`

```jsonc
{
    "action_type": "buy_pooch",
    "target_type": "owner",
    "parameters": {
        "vendor_selector": "random",
        "pooch_filter": { "min_health": 50 },
        "destination": "kennel",
        "value_multiplier": 0.8
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `vendor_id` | int | one of | Buy from this specific vendor |
| `vendor_selector` | string | one of | `"random"` — pick a random vendor from the owner's servers |
| `pooch_selector` | string | no | `"random"` (default) or `"selected"` — which pooch from the vendor's stock to buy |
| `pooch_filter` | object | no | Filter to narrow vendor stock candidates |
| `value_multiplier` | float | no | Multiply the purchase price by this factor (default: `1.0`) |
| `destination` | string | no | Where to deliver the pooch — same values as `create_pooch` (default: `"kennel"`). Ignored when `target_type` is `"kennel"`. |
| `selector` | string | yes (kennel) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` — selects which kennel to deliver to. Multi-kennel selectors use the first resolved kennel. |
| `filter` | object | no | Kennel filter — only used when `target_type` is `"kennel"` |
| `save_as` | string | no | Save the purchased pooch's ID into a named slot |

When `target_type` is `"kennel"`, the purchased pooch is placed directly into the resolved kennel. If the kennel is full, the pooch is left unhoused in town.

If no matching vendor or pooch is found, the action is a no-op.

---

#### `release_stray`

Removes a pooch from the owner's kennel and releases it into the stray pool for one of the owner's servers (chosen randomly). The pooch loses its owner and kennel assignment.

```jsonc
{
    "action_type": "release_stray",
    "target_type": "pooch",
    "parameters": {
        "selector": "random"
    }
}
```

Supports the same pooch-targeting parameters as other pooch actions (`selector`, `count`, `filter`, `save_as`, `save_kennel`, `use_saved`, `exclude_claimed`).

If the owner belongs to no servers, the action is a no-op.

---

#### `receive_stray`

Claims a stray pooch from one of the owner's servers and delivers it to the owner.

By default a random stray is chosen. If `use_saved` is set, the action instead resolves to whichever stray pooch IDs were stored in that context slot (e.g. by a prior `release_stray` with `save_as`).

**Supported target types:** `owner`, `kennel`

```jsonc
{
    "action_type": "receive_stray",
    "target_type": "owner",
    "parameters": {
        "destination": "kennel",
        "count": 1
    }
}
```

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `destination` | string | no | Where to deliver the stray — `"kennel"`, `"graveyard"`, `"hell"`, or `"town"` (default: `"kennel"`). Ignored when `target_type` is `"kennel"`. |
| `count` | int | no | How many strays to sample as candidates before randomly picking one (default: `1`). Ignored when `use_saved` is set. |
| `use_saved` | string | no | Slot name to read saved pooch IDs from. When set, the pool is restricted to those specific stray IDs instead of picking randomly. |
| `selector` | string | yes (kennel) | `"random"`, `"selected"`, `"all"`, `"random_exclude"`, or `"all_exclude"` — selects which kennel to deliver to. Multi-kennel selectors use the first resolved kennel. |
| `filter` | object | no | Kennel filter — only used when `target_type` is `"kennel"` |

When `target_type` is `"kennel"`, the received stray is placed directly into the resolved kennel. If the kennel is full, the pooch is left unhoused in town.

If no strays are available (or none of the saved IDs are currently strays on the server), the action is a no-op.

**Example — receive the same pooch that was released earlier:**

```jsonc
[
    {
        "action_type": "release_stray",
        "target_type": "pooch",
        "parameters": {
            "selector": "selected",
            "save_as": "released_pooch"
        }
    },
    {
        "action_type": "receive_stray",
        "target_type": "owner",
        "parameters": {
            "destination": "kennel",
            "use_saved": "released_pooch"
        }
    }
]
```

---

### `exclude_claimed` Parameter

The `exclude_claimed` boolean parameter can be added to any pooch-targeting action. When set to `true`, the action participates in the **preflight cross-option uniqueness check** at trigger time:

1. For each visible event option (in definition order), the engine speculatively resolves any action with `exclude_claimed: true`, excluding pooch IDs already claimed by earlier options.
2. If a valid candidate is found, that pooch ID is "claimed" and stored internally so later options cannot resolve to the same pooch.
3. If no valid candidate remains for an option (all have been claimed), that option is suppressed and hidden from the player's response menu.

This ensures that when multiple options each claim a distinct stray (or any distinct pooch), each option genuinely resolves to a different animal, and options with no remaining candidate are automatically hidden.

```jsonc
{
    "action_type": "receive_stray",
    "target_type": "owner",
    "parameters": {
        "destination": "kennel",
        "exclude_claimed": true
    }
}
```

`exclude_claimed` is only meaningful on actions within **options** (not top-level event actions). It has no effect when used outside of the preflight context.
