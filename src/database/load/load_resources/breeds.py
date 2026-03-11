from typing import Any

from sqlalchemy import delete

from logger import get_logger

from ...models import Breed
from ...session import session_scope
from .utils import (
    RARITY_VALUES,
    RESOURCE_ROOT,
    ResourceValidationError,
    load_categorized_resource_objects,
)

logger = get_logger("database/load/load_resources/breeds")

_BREEDS_ROOT = RESOURCE_ROOT / "breeds"


def _validate_breeds_json(breeds_json: dict[str, dict[str, dict[str, Any]]]) -> None:
    errors: list[str] = []
    allowed_keys = {"alt_name", "description", "rarity", "advanced_options"}
    if not isinstance(breeds_json, dict):
        raise ResourceValidationError("Invalid breed resources: root value must be an object keyed by category")
    for category_name, breeds in breeds_json.items():
        category_path = f"breeds.{category_name}"
        if not isinstance(breeds, dict):
            errors.append(f"{category_path}: category value must be an object keyed by breed name")
            continue
        for breed_name, attributes in breeds.items():
            path = f"{category_path}.{breed_name}"
            if not isinstance(attributes, dict):
                errors.append(f"{path}: breed definition must be an object")
                continue
            unknown = sorted(set(attributes) - allowed_keys)
            if unknown:
                errors.append(f"{path}: contains unknown keys: {', '.join(unknown)}")
            alt_name = attributes.get("alt_name")
            if alt_name is not None and (not isinstance(alt_name, str) or not alt_name.strip()):
                errors.append(f"{path}.alt_name: must be a non-blank string when provided")
            description = attributes.get("description")
            if description is not None and not isinstance(description, str):
                errors.append(f"{path}.description: must be a string")
            rarity = attributes.get("rarity")
            if rarity is not None and (not isinstance(rarity, str) or rarity.strip().lower() not in RARITY_VALUES):
                errors.append(f"{path}.rarity: must be one of: {', '.join(sorted(RARITY_VALUES))}")
            advanced_options = attributes.get("advanced_options")
            if advanced_options is not None and not isinstance(advanced_options, dict):
                errors.append(f"{path}.advanced_options: must be an object")
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ResourceValidationError(f"Invalid breed resources:\n{joined}")


async def load_breeds():
    logger.info("Loading breeds from 'resources/breeds/**/*.jsonc' into the database...")

    breeds_json = load_categorized_resource_objects(_BREEDS_ROOT, "breed")
    _validate_breeds_json(breeds_json)

    async with session_scope() as session:
        await session.execute(delete(Breed))

        for breed_category, breeds in breeds_json.items():
            for breed, attributes in breeds.items():
                session.add(
                    Breed(
                        name=str(breed),
                        alt_name=str(attributes.get("alt_name", str(breed))),
                        category=str(breed_category),
                        description=str(attributes.get("description", f"{str(breed).capitalize()} is a type of dog.")),
                        rarity=str(attributes.get("rarity", "common")).lower(),
                        advanced_options=attributes.get("advanced_options", {}),
                    )
                )

    logger.info("Finished loading breeds.")
