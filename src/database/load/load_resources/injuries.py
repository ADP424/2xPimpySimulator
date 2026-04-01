from typing import Any

from sqlalchemy import delete

from src.database.session import session_scope
from src.logger import get_logger

from ...models import Injury
from .utils import (
    EVENT_SEVERITY_VALUES,
    HEALTH_IMPACT_VALUES,
    RESOURCE_ROOT,
    ResourceValidationError,
    load_categorized_resource_objects,
)

logger = get_logger("database/load/load_resources/injuries")

_INJURIES_ROOT = RESOURCE_ROOT / "injuries"

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
_ALLOWED_PARAM_KEYS = _STAT_PARAM_KEYS | {"max_duplicates", "persistence", "stacks"}
_ALLOWED_STACK_KEYS = _STAT_PARAM_KEYS | {"min_count", "max_count"}


_TREATED_ALLOWED_KEYS = _STAT_PARAM_KEYS | {"health_impact", "description", "max_duplicates", "persistence", "stacks"}


def _validate_parameters_dict(path: str, parameters: dict, allowed_param_keys: set, errors: list[str]) -> None:
    """Validate a parameters dict (shared between injury body and treated block)."""
    unknown_params = sorted(set(parameters) - allowed_param_keys)
    if unknown_params:
        errors.append(f"{path}: contains unknown keys: {', '.join(unknown_params)}")
    max_duplicates = parameters.get("max_duplicates")
    if max_duplicates is not None and (not isinstance(max_duplicates, int) or max_duplicates < 1):
        errors.append(f"{path}.max_duplicates: must be a positive integer")
    persistence = parameters.get("persistence")
    if persistence is not None and (not isinstance(persistence, int) or persistence < 1):
        errors.append(f"{path}.persistence: must be a positive integer")
    health_impact = parameters.get("health_impact")
    if health_impact is not None and str(health_impact).lower() not in HEALTH_IMPACT_VALUES:
        errors.append(f"{path}.health_impact: invalid value '{health_impact}'")
    description = parameters.get("description")
    if description is not None and not isinstance(description, str):
        errors.append(f"{path}.description: must be a string")
    stacks = parameters.get("stacks")
    if stacks is not None:
        if not isinstance(stacks, list):
            errors.append(f"{path}.stacks: must be a list")
        else:
            for i, entry in enumerate(stacks):
                entry_path = f"{path}.stacks[{i}]"
                if not isinstance(entry, dict):
                    errors.append(f"{entry_path}: each stack entry must be an object")
                    continue
                unknown_stack = sorted(set(entry) - _ALLOWED_STACK_KEYS)
                if unknown_stack:
                    errors.append(f"{entry_path}: contains unknown keys: {', '.join(unknown_stack)}")
                min_count = entry.get("min_count")
                if min_count is not None and (not isinstance(min_count, int) or min_count < 1):
                    errors.append(f"{entry_path}.min_count: must be a positive integer")
                max_count = entry.get("max_count")
                if max_count is not None and (not isinstance(max_count, int) or max_count < 1):
                    errors.append(f"{entry_path}.max_count: must be a positive integer")
                if isinstance(min_count, int) and isinstance(max_count, int) and min_count > max_count:
                    errors.append(f"{entry_path}: min_count ({min_count}) must not exceed max_count ({max_count})")
                for key, value in entry.items():
                    if key in ("min_count", "max_count"):
                        continue
                    if not isinstance(value, (int, float)):
                        errors.append(f"{entry_path}.{key}: must be a number")
    for key, value in parameters.items():
        if key in ("max_duplicates", "persistence", "stacks", "health_impact", "description"):
            continue
        if not isinstance(value, (int, float)):
            errors.append(f"{path}.{key}: must be a number")


def _validate_injuries_json(injuries_json: dict[str, dict[str, dict[str, Any]]]) -> None:
    errors: list[str] = []
    allowed_keys = {
        "health_impact",
        "severity",
        "description",
        "parameters",
        "treated",
        "visible",
        "invisible_messages",
        "reveal_chance",
    }
    allowed_param_keys = _ALLOWED_PARAM_KEYS
    if not isinstance(injuries_json, dict):
        raise ResourceValidationError("Invalid injury resources: root value must be an object keyed by category")
    for category_name, injuries in injuries_json.items():
        category_path = f"injuries.{category_name}"
        if not isinstance(injuries, dict):
            errors.append(f"{category_path}: category value must be an object keyed by injury name")
            continue
        for injury_name, attributes in injuries.items():
            path = f"{category_path}.{injury_name}"
            if not isinstance(attributes, dict):
                errors.append(f"{path}: injury definition must be an object")
                continue
            unknown = sorted(set(attributes) - allowed_keys)
            if unknown:
                errors.append(f"{path}: contains unknown keys: {', '.join(unknown)}")
            health_impact = attributes.get("health_impact")
            if health_impact is None:
                errors.append(f"{path}: missing required key 'health_impact'")
            elif str(health_impact).lower() not in HEALTH_IMPACT_VALUES:
                errors.append(f"{path}: invalid health_impact '{health_impact}'")
            severity = attributes.get("severity")
            if severity is not None and str(severity).lower() not in EVENT_SEVERITY_VALUES:
                errors.append(f"{path}: invalid severity '{severity}'")
            description = attributes.get("description")
            if description is not None and not isinstance(description, str):
                errors.append(f"{path}.description: must be a string")
            parameters = attributes.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                errors.append(f"{path}.parameters: must be an object")
            elif isinstance(parameters, dict):
                _validate_parameters_dict(f"{path}.parameters", parameters, allowed_param_keys, errors)
            treated = attributes.get("treated")
            if treated is not None and not isinstance(treated, dict):
                errors.append(f"{path}.treated: must be an object")
            elif isinstance(treated, dict):
                _validate_parameters_dict(f"{path}.treated", treated, _TREATED_ALLOWED_KEYS, errors)
            visible = attributes.get("visible")
            if visible is not None and not isinstance(visible, bool):
                errors.append(f"{path}.visible: must be a boolean")
            invisible_messages = attributes.get("invisible_messages")
            if invisible_messages is not None:
                if not isinstance(invisible_messages, list):
                    errors.append(f"{path}.invisible_messages: must be a list of strings")
                else:
                    for i, msg in enumerate(invisible_messages):
                        if not isinstance(msg, str):
                            errors.append(f"{path}.invisible_messages[{i}]: must be a string")
            reveal_chance = attributes.get("reveal_chance")
            if reveal_chance is not None:
                if not isinstance(reveal_chance, (int, float)):
                    errors.append(f"{path}.reveal_chance: must be a number")
                elif not (0.0 <= float(reveal_chance) <= 1.0):
                    errors.append(f"{path}.reveal_chance: must be between 0.0 and 1.0")
    if errors:
        joined = "\n".join(f"- {e}" for e in errors)
        raise ResourceValidationError(f"Invalid injury resources:\n{joined}")


async def load_injuries():
    """
    Load injuries.

    Returns
    -------
    Any
        The result of calling `load_injuries`.
    """

    logger.info("Loading injuries from resources into the database...")

    injuries_json = load_categorized_resource_objects(_INJURIES_ROOT, "injury")
    _validate_injuries_json(injuries_json)

    async with session_scope() as session:
        await session.execute(delete(Injury))
        for injuries in injuries_json.values():
            for name, attributes in injuries.items():
                invisible_messages = attributes.get("invisible_messages")
                session.add(
                    Injury(
                        name=name,
                        health_impact=str(attributes["health_impact"]).lower(),
                        severity=str(attributes.get("severity", "minor")).lower(),
                        description=str(attributes.get("description", "")),
                        parameters=attributes.get("parameters", {}),
                        treated=attributes.get("treated") or None,
                        visible=bool(attributes.get("visible", True)),
                        invisible_messages=invisible_messages if isinstance(invisible_messages, list) else None,
                        reveal_chance=float(attributes.get("reveal_chance", 1.0)),
                    )
                )

    logger.info("Finished loading injuries.")
