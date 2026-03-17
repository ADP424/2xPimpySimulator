from typing import Any

from sqlalchemy import delete

from src.logger import get_logger

from ...models import Mutation
from ...session import session_scope
from .utils import (
    HEALTH_IMPACT_VALUES,
    RARITY_VALUES,
    RESOURCE_ROOT,
    ResourceValidationError,
    load_categorized_resource_objects,
)

logger = get_logger("database/load/load_resources/mutations")

_MUTATIONS_ROOT = RESOURCE_ROOT / "mutations"


def _validate_mutations_json(mutations_json: dict[str, dict[str, dict[str, Any]]]) -> None:
    errors: list[str] = []
    allowed_keys = {
        "alt_name",
        "description",
        "heritability",
        "health_impact",
        "rarity",
        "affects_males",
        "affects_females",
        "parameters",
    }
    if not isinstance(mutations_json, dict):
        raise ResourceValidationError("Invalid mutation resources: root value must be an object keyed by category")
    for category_name, mutations in mutations_json.items():
        category_path = f"mutations.{category_name}"
        if not isinstance(mutations, dict):
            errors.append(f"{category_path}: category value must be an object keyed by mutation name")
            continue
        for mutation_name, attributes in mutations.items():
            path = f"{category_path}.{mutation_name}"
            if not isinstance(attributes, dict):
                errors.append(f"{path}: mutation definition must be an object")
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
            heritability = attributes.get("heritability")
            if heritability is not None and not isinstance(heritability, (int, float)):
                errors.append(f"{path}.heritability: must be a number")
            health_impact = attributes.get("health_impact")
            if health_impact is not None and (
                not isinstance(health_impact, str) or health_impact.strip().lower() not in HEALTH_IMPACT_VALUES
            ):
                errors.append(f"{path}.health_impact: must be one of: {', '.join(sorted(HEALTH_IMPACT_VALUES))}")
            rarity = attributes.get("rarity")
            if rarity is not None and (not isinstance(rarity, str) or rarity.strip().lower() not in RARITY_VALUES):
                errors.append(f"{path}.rarity: must be one of: {', '.join(sorted(RARITY_VALUES))}")
            for field_name in ("affects_males", "affects_females"):
                field_value = attributes.get(field_name)
                if field_value is not None and not isinstance(field_value, bool):
                    errors.append(f"{path}.{field_name}: must be a boolean")
            parameters = attributes.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                errors.append(f"{path}.parameters: must be an object")
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ResourceValidationError(f"Invalid mutation resources:\n{joined}")


async def load_mutations():
    logger.info("Loading mutations from 'resources/mutations/**/*.jsonc' into the database...")

    mutations_json = load_categorized_resource_objects(_MUTATIONS_ROOT, "mutation")
    _validate_mutations_json(mutations_json)

    async with session_scope() as session:
        await session.execute(delete(Mutation))

        for mutation_category, mutations in mutations_json.items():
            for mutation, attributes in mutations.items():
                session.add(
                    Mutation(
                        name=str(mutation),
                        alt_name=str(attributes.get("alt_name", str(mutation))),
                        category=str(mutation_category),
                        description=str(
                            attributes.get("description", f"{str(mutation).capitalize()} is a mutation for dogs.")
                        ),
                        heritability=float(attributes.get("heritability", 25.0)),
                        health_impact=str(attributes.get("health_impact", "neutral")).lower(),
                        rarity=str(attributes.get("rarity", "common")).lower(),
                        affects_males=bool(attributes.get("affects_males", True)),
                        affects_females=bool(attributes.get("affects_females", True)),
                        parameters=attributes.get("parameters", {}),
                    )
                )

    logger.info("Finished loading mutations.")
