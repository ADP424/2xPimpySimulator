# Server Event Guide

## Structure

### JSON

Server events are structured within `resources/server_events/**/*.jsonc` and grouped by category, like:

```json
{
    "[category]": {
        "[server event name]": {
            "description": "string",
            "flavor_text": "string",
            "severity": "string",
            "rarity": "string",
            "min_owners": "int",
            "max_participants": "int",
            "resolution_strategy": "string",
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
                    "requires_pooch_selection": "bool",
                    "advanced_options": {},
                    "actions": [
                        {
                            "action_type": "string",
                            "target_type": "string",
                            "parameters": {}
                        }
                    ]
                }
            ],
            "outcomes": [
                {
                    "label": "string",
                    "description": "string",
                    "message": "string",
                    "min_rank": "int|null",
                    "max_rank": "int|null",
                    "chance": "float|null",
                    "advanced_options": {},
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
    }
}
```

### Event Parameters

#### Category

Server events are grouped by category at the top level of `resources/server_events/**/*.jsonc`.

A category is just a named bucket for organizing server events.

Examples:

- `"Competition"`
- `"Festival"`
- `"Disaster"`
- `"Community"`

#### Name

Each key under a category is the event name.

The optional `name` field may also be included inside the event body, but the key is the canonical source.

#### Description

`description` is the plain-language explanation of the server event.

#### Flavor Text

`flavor_text` is the immersive text shown alongside the event when it is announced.

#### Severity

`severity` controls how intense the event is presented in the UI.

Accepted values are the same severity values used by owner events.

#### Rarity

`rarity` controls how likely the event is to be selected relative to other eligible server events.

Accepted values are the same rarity values used by owner events.

#### Min Owners

`min_owners` is the minimum number of registered owners required in the server before the event can trigger.

#### Max Participants

`max_participants` is the participation cap for the event.

- `0` means unlimited participants.
- Any positive integer limits the number of owners who can join.

#### Resolution Strategy

`resolution_strategy` controls how participations are ranked when the event resolves.

Accepted values:

- `"random_winner"`
- `"selected_pooch_health"`
- `"participation_only"`

#### Parameters

`advanced_options` is an escape hatch for special-case metadata.

Keep it as an object.

### Actions

Server events use the same action schema as owner events.

Actions can appear at three levels:

- event-level `actions`
- option-level `actions`
- outcome-level `actions`

### Options

Server event `options` represent the choices owners can submit while the event is active.

Each option supports:

- `label`
- `description`
- `min_money`
- `min_bloodskulls`
- `requires_pooch_selection`
- `advanced_options`
- `actions`

If `requires_pooch_selection` is true, the player must choose one of their living pooches when participating.

### Outcomes

Server event `outcomes` are evaluated during resolution after all participations have been ranked.

Each outcome supports:

- `label`
- `description`
- `message`
- `min_rank`
- `max_rank`
- `chance`
- `advanced_options`
- `actions`

An outcome applies only when all of its gating rules match:

- the participant rank is within the configured rank range
- the chance roll succeeds, if `chance` is provided

### Resolution Notes

Server events resolve after their active window ends.

At resolution time, the game:

1. ranks participations using `resolution_strategy`
2. evaluates matching outcomes in `outcome_order`
3. applies outcome actions to each participation
4. stores a summary including winner owner IDs and winner pooch IDs

### Action Targeting

Use the same target types and action parameter conventions documented for owner events.

For dynamic runtime entities like owners, kennels, and pooches, do not hardcode database IDs in static server event JSON.
