# Basic Guide

## Structure

### JSON

Breeds are structured within resources/breeds/**/*.jsonc, like:
```json
"[category]": {
    "[breed name]": {
        "alt_name": "string",
        "description": "string",
        "rarity": "string",
        "advanced_options": {
            "[option]": "string/float/int/list"
        }
    },
    ...
}
```

#### Category
This is the name of the category the breed belongs to (for example, "miniature poodle" and "toy poodle" are both types of poodles). There can be any number of breeds in a category.

#### Breed Name
The common name of the breed, i.e. the main one that it should be referred to as.

#### Alt Name
An alternate name for the breed, like a scientific name, common/slang term, etc. For example, "Standard Poodle" has the alternate name of "Pudelin".

#### Description
A brief description of the breed. For example, for "Toy Poodle", the description is "The newest breed of poodle, developed in the 20th century. They weigh just 4-6 pounds and are under 10 inches tall. You frequently see them riding around in their owners' handbags."

#### Rarity
How relatively likely/unlikely it is for a pooch to get this breed when generated in any way other than birth. There are eight categories of rarity corresponding to different levels of relative abundance. For example, "COMMON" has a relative abundance of 1000, while "RARE" has a relative abundance of 50, meaning a common breed is 20 times more likely to show up compared to a rare one.
- COMMON (1000)
- UNCOMMON (250)
- NOVEL (100)
- RARE (50)
- UNPRECEDENTED (25)
- REMARKABLE (10)
- EXTRAORDINARY (5)
- UNIQUE (1)

#### Parameters
An object representing more complex options for the breed (more information in "Parameters Guide").


# Parameters Guide

## Aquisition

### `born_from_ritual` : `bool`
Whether the breed can show up in pooches created by spending bloodskulls on the altar.
- `true`: The breed can show up in pooches created from sacrifice. This is the default.
- `false`: The breed will not show up in pooches created from sacrifice.

### `sold_by_vendors` : `bool`
Whether the breed can show up on pooches generated to be sold by vendors or not.
- `true`: The breed can show up in vendor pooches. This is the default.
- `false`: The breed will not show up in vendor pooches.

## Stats

Stat modifiers adjust the effective value of a pooch's stats based on its breed composition. Each breed's contribution is weighted by its relative proportion in the pooch (e.g. a 50% husky with `strength_add: 4` contributes +2 strength). The add modifier is applied before the mult modifier.

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
