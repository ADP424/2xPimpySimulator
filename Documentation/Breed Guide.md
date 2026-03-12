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

#### Advanced Options
An object representing more complex options for the breed (more information in "Advanced Options Guide").


# Advanced Options Guide

## Aquisition Options

### `born_from_ritual` : `bool (int)`
Whether the breed can show up in pooches created by spending bloodskulls on the altar.
- `1`: The breed can show up in pooches created from sacrifice. This is the default.
- `0`: The breed will not show up in pooches created from sacrifice.

### `sold_by_vendors` : `bool (int)`
Whether the breed can show up on pooches generated to be sold by vendors or not.
- `1`: The breed can show up in vendor pooches. This is the default.
- `0`: The breed will not show up in vendor pooches.
