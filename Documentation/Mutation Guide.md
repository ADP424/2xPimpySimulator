# Basic Guide

## Structure

### JSON

Mutations are structured within resources/mutations/**/*.jsonc, like:
```jsonc
"[category]": {
    "[mutation name]": {
        "alt_name": "string",
        "description": "string",
        "heritability": "float",
        "health_impact": "string",
        "rarity": "string",
        "parameters": {
            "[option]": "string/float/int/list"
        }
    },
    ...
}
```

#### Category
This is the name of the category the mutation belongs to (for example, "autism" and "schizophrenia" are both neurodevelopmental conditions). There can be any number of mutations in a category.

#### Mutation Name
The common name of the mutation, i.e. the main one that it should be referred to as.

#### Alt Name
An alternate name for the mutation, like a scientific name, common/slang term, etc. For example, "Polycystic Ovary Syndrome" has the alternate name of "Stein-Leventhal Syndrome".

#### Description
A brief description of the mutation, framed like it's describing the pooch with it. For example, for "Total Blindness", the description is "This pooch has never known what it's like to see."

#### Heritability
A floating point number between 0.0 and 1.0 (inclusive) representing the chance for a child of a pooch with this mutation to inherit it. This chance is doubled when both parents have it, to a maximum of 1.0 (guaranteed inheritance). So for example, if a mutation has 0.25 heritability, then there is a 25% chance a child will inherit it if only one parent has it, and a 50% chance the child will inherit it if both parents have it.

#### Health Impact
The positive/negative severity of the health impact the mutation has on the dog with it, written in all caps. There are 13 categories of health impact corresponding to different levels of numerical impact. For reference, a pooch has an average of 10 base health.
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

#### Rarity
How relatively likely/unlikely it is for a pooch to develop this mutation. There are eight categories of rarity corresponding to different levels of relative abundance. For example, "COMMON" has a relative abundance of 1000, while "RARE" has a relative abundance of 50, meaning a common mutation is 20 times more likely to show up compared to a rare one.
- `COMMON` (1000)
- `UNCOMMON` (250)
- `NOVEL` (100)
- `RARE` (50)
- `UNPRECEDENTED` (25)
- `REMARKABLE` (10)
- `EXTRAORDINARY` (5)
- `UNIQUE` (1)

#### Parameters
An object representing more complex options for the mutatation (more information in "Parameters Guide").


# Parameters Guide

## Aquisition

### `born_from_ritual` : `bool`
Whether the mutation can show up in pooches created by spending bloodskulls on the altar.
- `true`: The mutation can show up in pooches created from sacrifice. This is the default.
- `false`: The mutation will not show up in pooches created from sacrifice.

### `sold_by_vendors` : `bool`
Whether the mutation can show up on pooches generated to be sold by vendors or not.
- `true`: The mutation can show up in vendor pooches. This is the default.
- `false`: The mutation will not show up in vendor pooches.

## Breeding

### `breeding_cooldown` : `int`
How many more/fewer age cycles before the pooch can breed again. Added to the base breeding cooldown.


## Death

### `death_message` : `string`
A custom message to replace the standard one with when the pooch dies of this mutation.
- "[pooch]" is replaced by the name of the pooch with the mutation.

### `impact_message` : `string`
A custom message to replace the standard one with when this mutation impacts another pooch with an `on_death` effect.
- "[pooch]" is replaced with the name of the pooch with the mutation.
- "[victim]" is replaced with the name of the pooch affected by the mutation.

### `on_death` : `string`
An effect the pooch has on its targets when it dies (see `on_death_targets`).
- `kill`: Causes every target to immediately die.
- `spread`: Causes every target to immediately inherit this mutation.
- `spread_all`: Causes every target to immediately inherit ALL mutations the pooch with this mutation has.

### `on_death_chance` : `float`
The chance, as a float between 0 and 1, inclusive, that the `on_death` effect will happen.
This chance is rolled individually for each member in the `on_death_targets`.
The chance is 1.0 (100%) by default.

### `always_on_death` : `bool`
Whether the `on_death` effect should always trigger or only trigger if the mutation is the one that killed the pooch.
- `false`: The `on_death` will only trigger if it was this mutation that killed the pooch. This is the default.
- `true`: The `on_death` will trigger when the pooch dies, no matter what kills it.

### `on_death_targets` : `string`
If the pooch has an on_death impact, who are the targets?
- `none`: No targets. This is the default.
- `all`: Every other pooch in the kennel is a target.
- `random`: A random pooch in the kennel is a target.


## Heritability

### `incompatible_mutations` : `list[string]`
A list of names of other mutations the pooch cannot get if they have this mutation.<br>
You can also list mutation categories here.


## Stats

Stat modifiers adjust the effective value of a pooch's stats. The add modifier is applied before the mult modifier, and all mutations stack (adds sum, mults multiply together).

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


## Value

### `bloodskull_value_add` : `int`
A number to add to the pooch's bloodskull value (before multiplication).

### `bloodskull_value_mult` : `float`
A number to multiply the pooch's bloodskull value by (after addition).

### `dollar_value_add` : `int`
A number to add to the pooch's dollar value (before multiplication).

### `dollar_value_mult` : `float`
A number to multiply the pooch's dollar value by (after addition).
