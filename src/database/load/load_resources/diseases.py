from typing import Any

from sqlalchemy import delete

from src.database.session import session_scope
from src.logger import get_logger

from ...models import Disease
from .utils import (
    HEALTH_IMPACT_VALUES,
    RESOURCE_ROOT,
    ResourceValidationError,
    load_categorized_resource_objects,
)

logger = get_logger("database/load/load_resources/diseases")

_DISEASES_ROOT = RESOURCE_ROOT / "diseases"

_STATS = {
    "base_health",
    "strength",
    "cuteness",
    "fluffiness",
    "intelligence",
    "dexterity",
    "fertility",
    "aggressiveness",
    "constitution",
    "size",
}
_STAT_PARAM_KEYS = {f"{stat}_add" for stat in _STATS} | {f"{stat}_mult" for stat in _STATS}
_ALLOWED_PARAM_KEYS = _STAT_PARAM_KEYS | {"death_message"}

_VALID_SEASONS = {"spring", "summer", "autumn", "winter"}


def validate_diseases_json(diseases_json: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Validate the parsed disease resources structure.

    Parameters
    ----------
    diseases_json: dict
        The categorized disease JSON data to validate.

    Raises
    ------
    ResourceValidationError
        When any validation rule is violated.
    """

    errors: list[str] = []
    allowed_keys = {
        "health_impact",
        "description",
        "contagion_chance",
        "sexually_transmitted",
        "recovery_chance",
        "treatable",
        "curable",
        "immunity_duration",
        "heritability",
        "seasons",
        "season_contagion_modifiers",
        "parameters",
        "visible",
        "invisible_messages",
        "reveal_chance",
    }

    if not isinstance(diseases_json, dict):
        raise ResourceValidationError("Invalid disease resources: root value must be an object keyed by category")

    for category_name, diseases in diseases_json.items():
        category_path = f"diseases.{category_name}"
        if not isinstance(diseases, dict):
            errors.append(f"{category_path}: category value must be an object keyed by disease name")
            continue
        for disease_name, attributes in diseases.items():
            path = f"{category_path}.{disease_name}"
            if not isinstance(attributes, dict):
                errors.append(f"{path}: disease definition must be an object")
                continue

            unknown = sorted(set(attributes) - allowed_keys)
            if unknown:
                errors.append(f"{path}: contains unknown keys: {', '.join(unknown)}")

            # health_impact (required)
            health_impact = attributes.get("health_impact")
            if health_impact is None:
                errors.append(f"{path}: missing required key 'health_impact'")
            elif str(health_impact).lower() not in HEALTH_IMPACT_VALUES:
                errors.append(f"{path}: invalid health_impact '{health_impact}'")

            # description
            description = attributes.get("description")
            if description is not None and not isinstance(description, str):
                errors.append(f"{path}.description: must be a string")

            # contagion_chance
            contagion_chance = attributes.get("contagion_chance")
            if contagion_chance is not None:
                if not isinstance(contagion_chance, (int, float)):
                    errors.append(f"{path}.contagion_chance: must be a number")
                elif not (0.0 <= float(contagion_chance) <= 1.0):
                    errors.append(f"{path}.contagion_chance: must be between 0.0 and 1.0")

            # sexually_transmitted
            sexually_transmitted = attributes.get("sexually_transmitted")
            if sexually_transmitted is not None and not isinstance(sexually_transmitted, bool):
                errors.append(f"{path}.sexually_transmitted: must be a boolean")

            # recovery_chance
            recovery_chance = attributes.get("recovery_chance")
            if recovery_chance is not None:
                if not isinstance(recovery_chance, (int, float)):
                    errors.append(f"{path}.recovery_chance: must be a number")
                elif not (0.0 <= float(recovery_chance) <= 1.0):
                    errors.append(f"{path}.recovery_chance: must be between 0.0 and 1.0")

            # treatable
            treatable = attributes.get("treatable")
            if treatable is not None and not isinstance(treatable, bool):
                errors.append(f"{path}.treatable: must be a boolean")

            # curable
            curable = attributes.get("curable")
            if curable is not None and not isinstance(curable, bool):
                errors.append(f"{path}.curable: must be a boolean")

            # immunity_duration
            immunity_duration = attributes.get("immunity_duration")
            if immunity_duration is not None and (not isinstance(immunity_duration, int) or immunity_duration < 1):
                errors.append(f"{path}.immunity_duration: must be a positive integer")

            # heritability
            heritability = attributes.get("heritability")
            if heritability is not None:
                if not isinstance(heritability, (int, float)):
                    errors.append(f"{path}.heritability: must be a number")
                elif not (0.0 <= float(heritability) <= 1.0):
                    errors.append(f"{path}.heritability: must be between 0.0 and 1.0")

            # seasons
            seasons = attributes.get("seasons")
            if seasons is not None:
                if not isinstance(seasons, list):
                    errors.append(f"{path}.seasons: must be a list")
                else:
                    for s in seasons:
                        if not isinstance(s, str) or s.strip().lower() not in _VALID_SEASONS:
                            errors.append(
                                f"{path}.seasons: '{s}' is not a valid season "
                                f"(must be one of: {', '.join(sorted(_VALID_SEASONS))})"
                            )

            # season_contagion_modifiers
            season_mods = attributes.get("season_contagion_modifiers")
            if season_mods is not None:
                if not isinstance(season_mods, dict):
                    errors.append(f"{path}.season_contagion_modifiers: must be an object")
                else:
                    for season_key, mod_value in season_mods.items():
                        if season_key.lower() not in _VALID_SEASONS:
                            errors.append(f"{path}.season_contagion_modifiers: '{season_key}' is not a valid season")
                        if not isinstance(mod_value, (int, float)):
                            errors.append(f"{path}.season_contagion_modifiers.{season_key}: must be a number")

            # parameters
            parameters = attributes.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                errors.append(f"{path}.parameters: must be an object")
            elif isinstance(parameters, dict):
                unknown_params = sorted(set(parameters) - _ALLOWED_PARAM_KEYS)
                if unknown_params:
                    errors.append(f"{path}.parameters: contains unknown keys: {', '.join(unknown_params)}")
                death_message = parameters.get("death_message")
                if death_message is not None and not isinstance(death_message, str):
                    errors.append(f"{path}.parameters.death_message: must be a string")
                for key, value in parameters.items():
                    if key == "death_message":
                        continue
                    if not isinstance(value, (int, float)):
                        errors.append(f"{path}.parameters.{key}: must be a number")

            # visible
            visible = attributes.get("visible")
            if visible is not None and not isinstance(visible, bool):
                errors.append(f"{path}.visible: must be a boolean")

            # invisible_messages
            invisible_messages = attributes.get("invisible_messages")
            if invisible_messages is not None:
                if not isinstance(invisible_messages, list):
                    errors.append(f"{path}.invisible_messages: must be a list of strings")
                else:
                    for i, msg in enumerate(invisible_messages):
                        if not isinstance(msg, str):
                            errors.append(f"{path}.invisible_messages[{i}]: must be a string")

            # reveal_chance
            reveal_chance = attributes.get("reveal_chance")
            if reveal_chance is not None:
                if not isinstance(reveal_chance, (int, float)):
                    errors.append(f"{path}.reveal_chance: must be a number")
                elif not (0.0 <= float(reveal_chance) <= 1.0):
                    errors.append(f"{path}.reveal_chance: must be between 0.0 and 1.0")

    if errors:
        joined = "\n".join(f"- {e}" for e in errors)
        raise ResourceValidationError(f"Invalid disease resources:\n{joined}")


async def load_diseases():
    """Load disease resources from JSONC files into the database.

    Returns
    -------
    Any
        The result of calling `load_diseases`.
    """

    logger.info("Loading diseases from resources into the database...")

    diseases_json = load_categorized_resource_objects(_DISEASES_ROOT, "disease")
    validate_diseases_json(diseases_json)

    async with session_scope() as session:
        await session.execute(delete(Disease))
        for disease_category, diseases in diseases_json.items():
            for name, attributes in diseases.items():
                invisible_messages = attributes.get("invisible_messages")
                seasons = attributes.get("seasons")
                session.add(
                    Disease(
                        name=name,
                        category=str(disease_category),
                        description=str(attributes.get("description", "")),
                        health_impact=str(attributes["health_impact"]).lower(),
                        contagion_chance=float(attributes.get("contagion_chance", 0.0)),
                        sexually_transmitted=bool(attributes.get("sexually_transmitted", False)),
                        recovery_chance=float(attributes.get("recovery_chance", 0.0)),
                        treatable=bool(attributes.get("treatable", True)),
                        curable=bool(attributes.get("curable", True)),
                        immunity_duration=attributes.get("immunity_duration"),
                        heritability=float(attributes.get("heritability", 0.0)),
                        seasons=[s.lower() for s in seasons] if isinstance(seasons, list) else None,
                        season_contagion_modifiers=attributes.get("season_contagion_modifiers"),
                        parameters=attributes.get("parameters", {}),
                        visible=bool(attributes.get("visible", True)),
                        invisible_messages=invisible_messages if isinstance(invisible_messages, list) else None,
                        reveal_chance=float(attributes.get("reveal_chance", 1.0)),
                    )
                )

    logger.info("Finished loading diseases.")
