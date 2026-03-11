# Owner Event Guide

## Structure

### JSON

Owner events live in `resources/owner_events/**/*.jsonc`. Each event is its own file, placed inside a category subfolder. The category is determined by the folder name, not by any key in the file.

```json
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
    "advanced_options": {},
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
            "advanced_options": {},
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

### Advanced Options

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

```json
{
    "label": "string",
    "description": "string",
    "default": false,
    "visible": true,
    "filter": {},
    "advanced_options": {},
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

Whether this option is shown to the player.

- `true` (default): the option appears as a choice the player can select
- `false`: the option is hidden and can only execute on expiry (requires `"default": true`)

### Filter

Extra eligibility requirements for selecting this option.

If omitted or empty, the option has no additional restrictions beyond the event itself.

### Actions

Guaranteed actions that happen immediately when this option is selected (or executed on expiry).

### Outcomes

Chance-based branches that happen after the option's guaranteed actions.

If all outcomes have explicit `chance` values, they must sum to exactly `1.0`. If only some outcomes have explicit chances, the sum must not exceed `1.0` and the remaining weight is distributed among the implicit ones.

---

## Outcome Parameters

Outcomes are objects inside an option's `outcomes` list.

```json
{
    "chance": "float",
    "message": "string",
    "actions": []
}
```

### Chance

A floating point value between `0.0` and `1.0`.

### Message

The text shown if this outcome is selected.

### Actions

The actions that happen for this outcome.

---

# Filtering Guide

Owner events and owner-event options both use the same `filter` format.

An empty filter means no restrictions.

```json
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

```json
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
- `min_bloodskulls`
- `max_bloodskulls`
- `min_pooches`
- `max_pooches`
- `min_kennels`
- `max_kennels`
- `kennels`
- `pooches`

### Owner Counts

- `min_pooches` / `max_pooches` count all pooches owned by the owner, regardless of kennel placement
- `min_kennels` / `max_kennels` count all kennels owned by the owner

---

## Kennel Filter Objects

Kennel filter objects live inside `filter.kennels`.

```json
{
    "min_count": 1,
    "max_count": 3,
    "min_capacity": 2,
    "max_capacity": 8,
    "min_pooches": 1,
    "max_pooches": 5,
    "pooches": []
}
```

### Kennel Filter Fields

- `min_count`
- `max_count`
- `description`
- `min_capacity`
- `max_capacity`
- `min_pooches`
- `max_pooches`
- `pooches`

### Kennel Semantics

- `min_count` / `max_count` apply to the number of kennels matching that kennel filter
- `min_pooches` / `max_pooches` apply to the number of pooches currently in an individual kennel
- nested `pooches` filters apply only to pooches inside that kennel

---

## Pooch Filter Objects

Pooch filter objects live either:

- inside the top-level `filter.pooches`
- or inside a kennel filter's `pooches`

```json
{
    "min_count": 1,
    "max_count": 3,
    "min_age": 5,
    "max_age": 10,
    "sex": "female",
    "min_health": 3,
    "max_health": 8,
    "is_virgin": true,
    "is_alive": true,
    "min_breeding_cooldown": 0,
    "max_breeding_cooldown": 2,
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
- `sex`
- `min_health`
- `max_health`
- `is_virgin`
- `is_alive`
- `min_breeding_cooldown`
- `max_breeding_cooldown`
- `has_any_breed`
- `has_all_breeds`
- `exclude_breeds`
- `has_any_mutation`
- `has_all_mutations`
- `exclude_mutations`
- `location`

### Pooch Field Notes

- `health` uses the pooch's effective current health (`base_health - health_loss_age`)
- breed and mutation references are always by **name**, never by internal database ID
- `location` can be:
  - `"kennel"`: the pooch must currently be in a kennel
  - `"homeless"`: the pooch must not currently be in a kennel
  - `"any"`: no location restriction

For top-level `filter.pooches`, matching is across all pooches the owner owns.  
For nested kennel `pooches`, matching is only against pooches inside that kennel.

---

## Action Targeting Filters

Event actions can also include `parameters.filter` to narrow which targets are affected.

This depends on `target_type`.

If the action targets `"selected"`, the filter is ignored and the already-selected contextual target is used.

If the action targets `"random"`, the filter narrows the random pool.

If the action targets `"all_pooches"` or `"all_kennels"`, the filter narrows which objects are affected.

### Pooch Action Filters

Valid for:

- `target_type: "pooch"` with `parameters.pooch: "random"`
- `target_type: "all_pooches"`

Example:

```json
{
    "action_type": "set_breeding_cooldown",
    "target_type": "pooch",
    "parameters": {
        "pooch": "random",
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

Valid for:

- `target_type: "kennel"` with `parameters.kennel: "random"`
- `target_type: "all_kennels"`

Example:

```json
{
    "action_type": "modify_kennel_capacity",
    "target_type": "all_kennels",
    "parameters": {
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

## About `"selected"` and `"random"`

Dynamic runtime entities such as pooches and kennels should never be referenced by literal IDs in static event JSON.

Instead, use selector strings:

- `"selected"`: use the event's current contextual target
- `"random"`: choose a random matching target at action execution time

This is especially useful for events that need to refer to the same target across option branches and outcomes.

---

## Filtering Example

The following would live at `resources/owner_events/misfortune/escaped_pooch.jsonc`:

```json
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
                                "pooch": "selected"
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
                        "pooch": "selected"
                    }
                }
            ]
        }
    ]
}
```

---

## Action Reference

Actions are structured as:

```json
{
    "action_type": "string",
    "target_type": "string",
    "parameters": {}
}
```

### Supported Action Types

- `modify_money`
- `modify_bloodskulls`
- `modify_pooch_health`
- `modify_pooch_age`
- `kill_pooch`
- `add_mutation`
- `remove_mutation`
- `add_breed`
- `transfer_pooch`
- `create_pooch`
- `modify_kennel_capacity`
- `rename_pooch`
- `set_breeding_cooldown`
- `start_event`

### Supported Target Types

- `owner`
- `pooch`
- `kennel`
- `all_pooches`
- `all_kennels`

Static event JSON should reference stable content by name and dynamic runtime entities by selector strings.
