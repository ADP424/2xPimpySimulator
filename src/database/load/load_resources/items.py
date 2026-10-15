"""
Item resource loader.

Loads consumable items (cleaning products, dog food) from
``resources/items/<category>/*.jsonc`` into the ``items`` table.

Categories and their recognized parameters:

- ``cleaning``
    - ``price``: int, dollars cost at a vendor
    - ``mess_reduction``: int, how much kennel mess a single use removes
    - ``side_effect_health``: int, optional, applied to every pooch in the kennel
- ``food``
    - ``price``: int
    - ``food_units``: int, how much ``food_stock`` one item adds to a kennel
    - optional ``<stat>_add``: permanent stat bonus; each feeding gives every pooch in the kennel a small chance
      to gain it (see ``game.manage_items.feed_kennel``)
"""

from typing import Any

from sqlalchemy import delete

from src.database.session import session_scope
from src.logger import get_logger

from ...models import Item
from .utils import (
    RARITY_VALUES,
    RESOURCE_ROOT,
    ResourceValidationError,
    load_categorized_resource_objects,
)

logger = get_logger("database/load/load_resources/items")

_ITEMS_ROOT = RESOURCE_ROOT / "items"

_VALID_CATEGORIES = {"cleaning", "food"}

_STATS = {
    "strength",
    "cuteness",
    "fluffiness",
    "intelligence",
    "dexterity",
    "fertility",
    "aggressiveness",
    "constitution",
    "base_health",
}
_STAT_PARAM_KEYS = {f"{s}_add" for s in _STATS}

_ALLOWED_CLEANING_PARAMS = {
    "price",
    "mess_reduction",
    "side_effect_health",
}
_ALLOWED_FOOD_PARAMS = {
    "price",
    "food_units",
} | _STAT_PARAM_KEYS


def validate_items_json(items_json: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Validate the parsed item resource structure."""
    errors: list[str] = []
    allowed_top = {"alt_name", "description", "rarity", "parameters"}

    if not isinstance(items_json, dict):
        raise ResourceValidationError("Invalid item resources: root value must be an object keyed by category")

    for category_name, items in items_json.items():
        path_c = f"items.{category_name}"
        cat_key = str(category_name).strip().lower().replace(" ", "_")
        if cat_key not in _VALID_CATEGORIES:
            errors.append(f"{path_c}: unknown category (must be one of {sorted(_VALID_CATEGORIES)})")
        if not isinstance(items, dict):
            errors.append(f"{path_c}: value must be an object keyed by item name")
            continue
        for item_name, attributes in items.items():
            path = f"{path_c}.{item_name}"
            if not isinstance(attributes, dict):
                errors.append(f"{path}: item definition must be an object")
                continue
            unknown = sorted(set(attributes) - allowed_top)
            if unknown:
                errors.append(f"{path}: contains unknown keys: {', '.join(unknown)}")
            rarity = attributes.get("rarity")
            if rarity is not None and (not isinstance(rarity, str) or rarity.strip().lower() not in RARITY_VALUES):
                errors.append(f"{path}.rarity: must be one of: {', '.join(sorted(RARITY_VALUES))}")
            description = attributes.get("description")
            if description is not None and not isinstance(description, str):
                errors.append(f"{path}.description: must be a string")
            alt_name = attributes.get("alt_name")
            if alt_name is not None and not isinstance(alt_name, str):
                errors.append(f"{path}.alt_name: must be a string")

            parameters = attributes.get("parameters")
            if parameters is None:
                errors.append(f"{path}: 'parameters' is required")
                continue
            if not isinstance(parameters, dict):
                errors.append(f"{path}.parameters: must be an object")
                continue
            if cat_key == "cleaning":
                allowed = _ALLOWED_CLEANING_PARAMS
                if "price" not in parameters:
                    errors.append(f"{path}.parameters.price: required for cleaning items")
                if "mess_reduction" not in parameters:
                    errors.append(f"{path}.parameters.mess_reduction: required for cleaning items")
            elif cat_key == "food":
                allowed = _ALLOWED_FOOD_PARAMS
                if "price" not in parameters:
                    errors.append(f"{path}.parameters.price: required for food items")
                if "food_units" not in parameters:
                    errors.append(f"{path}.parameters.food_units: required for food items")
            else:
                allowed = set()

            unknown_params = sorted(set(parameters) - allowed)
            if unknown_params:
                errors.append(f"{path}.parameters: contains unknown keys: {', '.join(unknown_params)}")
            for k, v in parameters.items():
                if not isinstance(v, (int, float)):
                    errors.append(f"{path}.parameters.{k}: must be a number")
                elif k == "price" and v < 0:
                    errors.append(f"{path}.parameters.price: must be >= 0")
                elif k == "mess_reduction" and v < 0:
                    errors.append(f"{path}.parameters.mess_reduction: must be >= 0")
                elif k == "food_units" and v <= 0:
                    errors.append(f"{path}.parameters.food_units: must be > 0")

    if errors:
        joined = "\n".join(f"- {e}" for e in errors)
        raise ResourceValidationError(f"Invalid item resources:\n{joined}")


async def load_items():
    """Load item resources from JSONC files into the ``items`` table."""
    logger.info("Loading items from 'resources/items/**/*.jsonc' into the database...")

    if not _ITEMS_ROOT.exists():
        logger.info("No resources/items directory found; skipping item load.")
        return

    items_json = load_categorized_resource_objects(_ITEMS_ROOT, "item")
    validate_items_json(items_json)

    async with session_scope() as session:
        await session.execute(delete(Item))
        for category, items in items_json.items():
            # Category keys come in Title Case from the filesystem slug; we
            # persist them as a normalized lowercase string so runtime code
            # can do case-insensitive lookups.
            category_key = str(category).strip().lower().replace(" ", "_")
            for name, attributes in items.items():
                session.add(
                    Item(
                        name=name,
                        alt_name=str(attributes.get("alt_name", "")),
                        category=category_key,
                        description=str(attributes.get("description", "")),
                        rarity=str(attributes.get("rarity", "common")).lower(),
                        parameters=dict(attributes.get("parameters", {})),
                    )
                )

    logger.info("Finished loading items.")
