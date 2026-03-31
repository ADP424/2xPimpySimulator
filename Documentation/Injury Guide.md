# Basic Guide

## Structure

### JSON

Injuries are structured within resources/injuries/**/*.jsonc, like:
```jsonc
{
    "name": "string",
    "health_impact": "string",
    "description": "string",
    "visible": "bool",
    "invisible_messages": ["string", "..."],
    "parameters": {
        "[option]": "int/float"
    }
}
```

#### Name
The name of the injury, i.e. what it should be referred to as. Used when referencing the injury in event files via the `injure_pooch` action.

#### Health Impact
The positive/negative severity of the health impact the injury has on the pooch with it, written in all caps. There are 13 categories of health impact corresponding to different levels of numerical impact. For reference, a pooch has an average of 10 base health.
- `INSTANT_DEATH` (-1000)
- `FATAL` (-5)
- `BRUTAL` (-4)
- `SEVERE` (-3)
- `UNHEALTHY` (-2)
- `HARMFUL` (-1)
- `NEUTRAL` (0)
- `HELPFUL` (+1)
- `HEALTHY` (+2)
- `GREAT` (+3)
- `FANTASTIC` (+4)
- `BRILLIANT` (+5)
- `IMMORTALITY` (+1000)

#### Description
A brief description of the injury, framed like it's describing the pooch with it. For example, "This pooch is missing an eye."

#### Visible
Whether this injury is shown to the player on the pooch info screen. Defaults to `true`.
- `true`: The injury name appears in the pooch's injury list and is accessible via the dropdown. This is the default.
- `false`: The injury is hidden. Its name is never shown to the player. If `invisible_messages` is provided, one message is randomly chosen when the injury is applied and shown in the injury list in place of the name (the same message is always shown for that instance). If no `invisible_messages` are provided, the injury is entirely silent — the player sees nothing.

#### Invisible Messages
A list of possible symptom messages to display for this injury when it is invisible (`"visible": false`). Formatted the same as the description — written as if describing the pooch (e.g. `"This pooch is limping."`). One message is chosen at random when the injury is applied to a pooch and is shown persistently for that instance. Only used when `"visible": false`; has no effect on visible injuries.
- If omitted (or `"visible"` is `true`), nothing special happens. This is the default.
- Example: `"invisible_messages": ["This pooch is limping.", "This pooch favors its left side."]`

#### Parameters
An object representing more complex options for the injury (more information in "Parameters Guide").


# Parameters Guide

## Stacking

### `persistence` : `int`
How many hourly ticks it takes for this injury to heal on its own. Must be a positive integer. Each hour, a pooch has a chance equal to `constitution / 50` to decrement the persistence counter on each of their injuries that has one. When the counter reaches 0, the injury is automatically removed. This is the exact same formula as fertility reducing the breeding cooldown.
- If omitted, the injury is permanent and will never heal on its own. This is the default.
- Example: `"persistence": 24` — on average, a pooch with 10 constitution heals this injury in ~120 hours (5 days).

### `max_duplicates` : `int`
The maximum number of times this injury can be applied to the same pooch. Must be a positive integer.
- If omitted, the injury can be applied any number of times. This is the default.
- Example: `"max_duplicates": 2` — a pooch can have this injury at most twice (e.g. one missing eye per eye socket).

### `stacks` : `list[object]`
A list of threshold-based stat modifier entries that apply when the pooch has a certain number of this injury. Each entry fires independently when its count condition is met. Stat modifiers within stack entries work exactly the same as top-level stat parameters (adds sum, mults multiply together), and are applied after the per-instance effects.

Example:
```jsonc
"stacks": [
    {
        "min_count": 2,
        "dexterity_add": -5,
        "dexterity_mult": 0.5
    }
]
```

Each stack entry supports the following fields:

#### `min_count` : `int`
The minimum number of this injury the pooch must have for this entry to apply. Must be a positive integer. Defaults to 1.

#### `max_count` : `int`
The maximum number of this injury the pooch can have for this entry to apply. Must be a positive integer. If omitted, there is no upper bound.

Any stat `_add` or `_mult` parameter (see Stats section below) is also valid inside a stack entry.


## Stats

Stat modifiers adjust the effective value of a pooch's stats. The add modifier is applied before the mult modifier. Injuries are applied after mutations and breeds. All injuries stack (adds sum, mults multiply together).

The following `_add` (int) and `_mult` (float) parameters are available for each stat:

| Stat | Add parameter | Mult parameter |
|------|--------------|----------------|
| Base Health | `base_health_add` | `base_health_mult` |
| Strength | `strength_add` | `strength_mult` |
| Cuteness | `cuteness_add` | `cuteness_mult` |
| Fluffiness | `fluffiness_add` | `fluffiness_mult` |
| Intelligence | `intelligence_add` | `intelligence_mult` |
| Dexterity | `dexterity_add` | `dexterity_mult` |
| Fertility | `fertility_add` | `fertility_mult` |
| Aggressiveness | `aggressiveness_add` | `aggressiveness_mult` |
| Constitution | `constitution_add` | `constitution_mult` |
| Size | `size_add` | `size_mult` |
