# Event Guide

## Structure

### JSON

Events are structured within `resources/events.json` and grouped by category, like:

```json
{
    "[category]": {
        "[event name]": {
            "description": "string",
            "flavor_text": "string",
            "severity": "string",
            "rarity": "string",
            "requires_response": "bool",
            "response_timeout": "int",
            "min_pooches": "int",
            "min_kennels": "int",
            "min_money": "int",
            "min_bloodskulls": "int",
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
                    "min_money": "int",
                    "min_bloodskulls": "int",
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
    }
}
```

### Event Parameters

#### Category

Events are grouped by category at the top level of `resources/events.json`.

A category is just a named bucket for organizing events.

Examples:

- `"Fortune"`
- `"Misfortune"`
- `"Mutation"`
- `"Supernatural"`
- `"Breeding"`

---

#### Event Name

The name of the event. This is the primary name used to identify it.

Examples:

- `"Escaped Pooch"`
- `"Vet Bill"`
- `"Strange Mutation"`

---

#### Description

The main descriptive text for the event.

This explains what is happening and what the player is reacting to.

Example:

> "One of your pooches has escaped the kennel and run off into the neighborhood."

---

#### Flavor Text

Additional flavor text for the event.

This is optional and is mainly used to give the event more personality.

Example:

> "A neighbor swears they saw the pooch bolt down an alley near the market."

---

#### Severity

How impactful the event is.

Severity is used for balancing and categorizing how serious an event feels.

Current severity levels:

- `TRIVIAL`
- `MINOR`
- `MODERATE`
- `MAJOR`
- `CRITICAL`
- `REMARKABLE`
- `CATASTROPHIC`

Example guideline:

| Severity | Typical Impact |
|--------|--------|
| TRIVIAL | Mostly flavor, tiny changes |
| MINOR | Small stat or currency changes |
| MODERATE | Noticeable pooch or kennel impact |
| MAJOR | Losing pooches, major gains, or major setbacks |
| CRITICAL | Large consequences affecting important assets |
| REMARKABLE | Rare and dramatic outcomes |
| CATASTROPHIC | Extremely severe, game-changing events |

---

#### Rarity

How likely the event is to appear relative to other events.

Current rarity levels use relative weights:

- `COMMON` (1000)
- `UNCOMMON` (250)
- `NOVEL` (100)
- `RARE` (50)
- `UNPRECEDENTED` (25)
- `REMARKABLE` (10)
- `EXTRAORDINARY` (5)
- `UNIQUE` (1)

These are relative weights, not direct percentages.

For example:

A `COMMON` event is **20 times more likely** to be selected than a `RARE` event.

---

#### Requires Response

Whether the event waits for the player to choose an option.

- `true`: the player must respond, or the event will time out
- `false`: the event resolves immediately using its top-level `actions`

Response events should define at least one option.

---

#### Response Timeout

How long the player has to respond, in **seconds**.

Example:

```json
"response_timeout": 7200
```

For response events:
- if the player responds in time, the chosen option resolves
- if the player does not respond in time, the event's top-level `actions` are used as the timeout/default result

---

#### Min Pooches

The minimum number of pooches the owner must have to be eligible for the event.

Example:

```json
"min_pooches": 1
```

---

#### Min Kennels

The minimum number of kennels the owner must have to be eligible for the event.

---

#### Min Money

The minimum amount of money the owner must have to be eligible for the event.

---

#### Min Bloodskulls

The minimum number of bloodskulls the owner must have to be eligible for the event.

---

#### Advanced Options

A free-form object for additional event configuration.

This is intended for more specialized event behavior and future extensions.

Example:

```json
"advanced_options": {
    "some_flag": true,
    "some_value": 2
}
```

---

#### Actions

Top-level event actions.

These behave differently depending on whether the event requires a response:

- if `requires_response` is `false`, these happen immediately when the event triggers
- if `requires_response` is `true`, these happen if the event expires without a response

Example:

```json
"actions": [
    {
        "action_type": "modify_pooch_health",
        "target_type": "pooch",
        "parameters": {
            "pooch_id": "random",
            "amount": -2
        }
    }
]
```

---

#### Options

The list of response options the player can choose from.

This is mainly used for response events.

Example:

```json
"options": [
    {
        "label": "Search Yourself",
        "description": "Look for the pooch around the neighborhood.",
        "outcomes": [
            {
                "chance": 0.7,
                "message": "You find the pooch hiding behind a dumpster.",
                "actions": []
            },
            {
                "chance": 0.3,
                "message": "You search everywhere but the pooch is gone.",
                "actions": [
                    {
                        "action_type": "kill_pooch",
                        "target_type": "pooch",
                        "parameters": {
                            "pooch_id": "selected"
                        }
                    }
                ]
            }
        ]
    }
]
```

---

### Option Parameters

Options are objects inside an event's `options` list.

```json
{
    "label": "string",
    "description": "string",
    "min_money": "int",
    "min_bloodskulls": "int",
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
            "actions": []
        }
    ]
}
```

---

#### Label

The text shown to the player for this option.

Examples:

- `"Search Yourself"`
- `"Hire Search Party"`
- `"Give Up"`

---

#### Description

A short explanation of what choosing the option means.

This is also used in the Discord bot UI.

Example:

> "Spend some time searching the nearby streets yourself."

---

#### Min Money

The minimum amount of money the player must have to select this option.

If the player does not meet the requirement, the option cannot be selected.

---

#### Min Bloodskulls

The minimum number of bloodskulls the player must have to select this option.

---

#### Advanced Options

A free-form object for additional option configuration.

---

#### Actions

A guaranteed list of actions that happens immediately when this option is selected.

Use these for effects that should always happen regardless of which outcome branch is rolled.

Examples:

- charging money to hire a search party
- spending a resource up front
- setting up some guaranteed state change before branching happens

Example:

```json
"actions": [
    {
        "action_type": "modify_money",
        "target_type": "owner",
        "parameters": {
            "amount": -100
        }
    }
]
```

---

#### Outcomes

A list of possible branches for the selected option.

Each outcome has:
- a `chance`
- a `message`
- its own list of `actions`

This allows an option to have success/failure paths or any other branching result.

If an option uses outcomes, outcome chances should add up to **1.0**.

Example:

```json
"outcomes": [
    {
        "chance": 0.7,
        "message": "You eventually track the pooch down and bring them home safely.",
        "actions": []
    },
    {
        "chance": 0.3,
        "message": "Despite your efforts, the pooch is never found.",
        "actions": [
            {
                "action_type": "kill_pooch",
                "target_type": "pooch",
                "parameters": {
                    "pooch_id": "selected"
                }
            }
        ]
    }
]
```

If an option has both `actions` and `outcomes`, the usual pattern is:

1. option `actions` happen first
2. one outcome is rolled
3. the chosen outcome's `actions` happen
4. the outcome's `message` is shown to the player

---

### Outcome Parameters

Outcomes are objects inside an option's `outcomes` list.

```json
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
```

---

#### Chance

A floating point number between `0.0` and `1.0`.

This is the probability that this outcome occurs when the option is selected.

Example:

```json
"chance": 0.25
```

---

#### Message

The custom message shown to the player if this outcome is selected.

This should describe what happened.

Examples:

- `"You find the escaped pooch hiding under a parked truck."`
- `"The search turns up nothing, and the pooch is never seen again."`
- `"The mutation fades on its own after a few days."`

This is what should be shown instead of generic fallback text like `"No recorded outcome."`

---

#### Actions

The list of actions that occur if this outcome is selected.

These are structured the same way as normal event actions.

---

### Action Parameters

Actions are structured as objects inside:
- event `actions`
- option `actions`
- outcome `actions`

```json
{
    "action_type": "string",
    "target_type": "string",
    "parameters": {}
}
```

---

#### Action Type

What the action does.

Current supported action types:

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

---

#### Target Type

Who or what the action affects.

Current supported target types:

- `owner`
- `pooch`
- `kennel`
- `all_pooches`
- `all_kennels`

Note: `pooch` and `kennel` actions use selector parameters to decide whether they target the currently selected entity or a randomly chosen one. Not every action type supports every target type.

---

#### Parameters

An object containing the settings for the action.

The valid parameters depend on the action type.

Static event JSON should only directly reference stable static content by name. Dynamic runtime entities such as pooches, kennels, owners, or vendors should be targeted through contextual selector strings rather than literal IDs.

---

# Action Reference

## Money Actions

### `modify_money`

Changes the owner's money.

Allowed target types:
- `owner`

Allowed parameters:
- `amount` : `int`
- `min_amount` : `int`
- `max_amount` : `int`

You must provide either:
- `amount`

or:
- `min_amount` and `max_amount`

Example:

```json
{
    "action_type": "modify_money",
    "target_type": "owner",
    "parameters": {
        "amount": -100
    }
}
```

---

### `modify_bloodskulls`

Changes the owner's bloodskulls.

Allowed target types:
- `owner`

Allowed parameters:
- `amount` : `int`
- `min_amount` : `int`
- `max_amount` : `int`

You must provide either:
- `amount`

or:
- `min_amount` and `max_amount`

---

## Pooch Stat Actions

### `modify_pooch_health`

Changes a pooch's health.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `amount` : `int`
- `min_amount` : `int`
- `max_amount` : `int`

`pooch_id` is required when `target_type` is `pooch`.

`pooch_id` can be:
- `"selected"`
- `"random"`

You must provide either:
- `amount`

or:
- `min_amount` and `max_amount`

---

### `modify_pooch_age`

Changes a pooch's age.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `amount` : `int`
- `min_amount` : `int`
- `max_amount` : `int`

`pooch_id` is required when `target_type` is `pooch`.

`pooch_id` can be:
- `"selected"`
- `"random"`

You must provide either:
- `amount`

or:
- `min_amount` and `max_amount`

---

### `kill_pooch`

Kills one or more pooches.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`

`pooch_id` is required when `target_type` is `pooch`.

`pooch_id` can be:
- `"selected"`
- `"random"`

---

## Mutation and Breed Actions

### `add_mutation`

Adds a mutation to one or more pooches.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `mutation` : `string`

`pooch_id` is required when `target_type` is `pooch`.

If `mutation` is omitted, the game chooses a mutation. Reference the mutation by name.

---

### `remove_mutation`

Removes a mutation from one or more pooches.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `mutation` : `string`

`pooch_id` is required when `target_type` is `pooch`.

If `mutation` is omitted, the game chooses a mutation to remove. Reference the mutation by name.

---

### `add_breed`

Adds a breed to one or more pooches.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `breed` : `string`
- `weight` : `int|float`

`pooch_id` is required when `target_type` is `pooch`.

If `breed` is omitted, the game chooses a breed.

Static events should reference breeds by name, not by internal database ID. The loader resolves the name to the correct database row when resources are loaded.

`weight` must be greater than `0`.

---

## Ownership and Kennel Actions

### `transfer_pooch`

Transfers a pooch to another owner or a vendor.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `new_owner_discord_id` : `int`
- `vendor_id` : `int`

`pooch_id` is required when `target_type` is `pooch`.

You must provide exactly one of:
- `new_owner_discord_id`
- `vendor_id`

---

### `create_pooch`

Creates a new pooch.

Allowed target types:
- `owner`

Allowed parameters:
- `name` : `string`
- `sex` : `string`
- `age` : `int`
- `base_health` : `int`
- `breeding_cooldown` : `int`

If omitted, the game uses its normal generation defaults for unspecified values.

---

### `modify_kennel_capacity`

Changes a kennel's pooch limit.

Allowed target types:
- `kennel`
- `all_kennels`

Allowed parameters:
- `kennel_id` : `string`
- `amount` : `int`
- `min_amount` : `int`
- `max_amount` : `int`

`kennel_id` is required when `target_type` is `kennel`.

`kennel_id` can be:
- `"selected"`
- `"random"`

You must provide either:
- `amount`

or:
- `min_amount` and `max_amount`

---

## Utility Actions

### `rename_pooch`

Renames one or more pooches.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `name` : `string`

`pooch_id` is required when `target_type` is `pooch`.

`name` is required.

---

### `set_breeding_cooldown`

Sets a pooch's breeding cooldown.

Allowed target types:
- `pooch`
- `all_pooches`

Allowed parameters:
- `pooch_id` : `string`
- `cooldown` : `int`

`pooch_id` is required when `target_type` is `pooch`.

`cooldown` is required.

---

# Database Notes

## Event Actions Table

The backend schema uses one `event_actions` table for all actions.

Each action belongs to exactly one of:
- an event
- an option
- an outcome

This means every row should have exactly one non-null parent reference:
- `event_id`
- `option_id`
- `outcome_id`

This allows:
- top-level event actions
- guaranteed option actions
- chance-based outcome actions

without needing separate action tables.

---

## Event Outcomes Table

Chance-based branches for options are represented as event outcomes in the database.

Each outcome belongs to an option and stores:
- `option_id`
- `chance`
- `message`

An outcome can also have its own linked actions through `event_actions`.

---

# Rules and Validation Notes

## General Rules

- Categories must be objects.
- Event definitions must be objects.
- Option definitions must be objects.
- Outcome definitions must be objects.
- Action definitions must be objects.
- Events must define at least one top-level `action` or at least one `option`.
- Events with `requires_response: true` should define at least one option.
- `response_timeout` must be at least `1` if present.
- `min_pooches`, `min_kennels`, `min_money`, and `min_bloodskulls` must be `0` or greater.
- Option `min_money` and `min_bloodskulls` must be `0` or greater.
- Outcome `chance` values should add up to `1.0` for a well-formed branching option.
- Unknown keys should be treated as invalid.

---

## About `"selected"`

For dynamic runtime entities like pooches and kennels, static events should never use literal database IDs.

Instead, use selector strings:
- `"selected"` to use the event's current contextual target
- `"random"` to use a random contextual target chosen by the event system

This keeps static event JSON stable even though runtime entities are created and deleted over time.

This is especially useful for:
- escaped pooch events
- response branches that need to refer to the same pooch throughout the event
- events with success/failure outcomes that both reference the same chosen target

---

# Example Event

```json
{
    "Misfortune": {
        "Escaped Pooch": {
            "description": "One of your pooches has escaped the kennel.",
            "flavor_text": "A neighbor says they saw the pooch sprint down the street an hour ago.",
            "severity": "MODERATE",
            "rarity": "UNCOMMON",
            "requires_response": true,
            "response_timeout": 7200,
            "min_pooches": 1,
            "options": [
                {
                    "label": "Search Yourself",
                    "description": "Look for the pooch around the neighborhood.",
                    "outcomes": [
                        {
                            "chance": 0.7,
                            "message": "You find the pooch hiding behind a dumpster and bring them home.",
                            "actions": []
                        },
                        {
                            "chance": 0.3,
                            "message": "You search everywhere, but the pooch is never found.",
                            "actions": [
                                {
                                    "action_type": "kill_pooch",
                                    "target_type": "pooch",
                                    "parameters": {
                                        "pooch_id": "selected"
                                    }
                                }
                            ]
                        }
                    ]
                },
                {
                    "label": "Hire Search Party",
                    "description": "Pay professionals to help track the pooch down.",
                    "min_money": 100,
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
                            "message": "The search party finds the pooch and safely returns them.",
                            "actions": []
                        },
                        {
                            "chance": 0.1,
                            "message": "Even with help, the pooch is never found.",
                            "actions": [
                                {
                                    "action_type": "kill_pooch",
                                    "target_type": "pooch",
                                    "parameters": {
                                        "pooch_id": "selected"
                                    }
                                }
                            ]
                        }
                    ]
                },
                {
                    "label": "Give Up",
                    "description": "Accept that the pooch is gone.",
                    "outcomes": [
                        {
                            "chance": 1.0,
                            "message": "The pooch is never seen again.",
                            "actions": [
                                {
                                    "action_type": "kill_pooch",
                                    "target_type": "pooch",
                                    "parameters": {
                                        "pooch_id": "selected"
                                    }
                                }
                            ]
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "action_type": "kill_pooch",
                    "target_type": "pooch",
                    "parameters": {
                        "pooch_id": "selected"
                    }
                }
            ]
        }
    }
}
```

In this example:

- the event belongs to the `"Misfortune"` category
- it requires a response
- the player has 7200 seconds to respond
- if the player chooses an option, any guaranteed option `actions` happen first
- then one of that option's `outcomes` is rolled
- the outcome `message` is shown
- the outcome `actions` are applied
- if the player does not respond in time, the event's top-level `actions` happen instead