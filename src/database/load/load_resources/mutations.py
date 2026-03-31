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


_VALID_SEASONS = {"spring", "summer", "autumn", "winter"}
_VALID_ON_DEATH_EFFECTS = {"kill", "spread", "spread_all", "send_to_hell", "none"}
_VALID_ON_DEATH_TARGETS = {"all", "random", "none"}
_VALID_ON_DEATH_TRIGGER_KEYS = {
    "on_death",
    "on_death_targets",
    "on_death_chance",
    "always_on_death",
    "impact_message",
}


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
        "visible",
        "invisible_messages",
        "reveal_chance",
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
            parameters = attributes.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                errors.append(f"{path}.parameters: must be an object")
            elif isinstance(parameters, dict):
                seasons = parameters.get("seasons")
                if seasons is not None:
                    if not isinstance(seasons, list):
                        errors.append(f"{path}.parameters.seasons: must be a list")
                    else:
                        for s in seasons:
                            if not isinstance(s, str) or s.strip().lower() not in _VALID_SEASONS:
                                errors.append(
                                    f"{path}.parameters.seasons: '{s}' is not a valid season "
                                    f"(must be one of: {', '.join(sorted(_VALID_SEASONS))})"
                                )
                on_death_triggers = parameters.get("on_death_triggers")
                if on_death_triggers is not None:
                    if not isinstance(on_death_triggers, list):
                        errors.append(f"{path}.parameters.on_death_triggers: must be a list")
                    else:
                        for i, trigger in enumerate(on_death_triggers):
                            trigger_path = f"{path}.parameters.on_death_triggers[{i}]"
                            if not isinstance(trigger, dict):
                                errors.append(f"{trigger_path}: each trigger must be an object")
                                continue
                            unknown_trigger_keys = sorted(set(trigger) - _VALID_ON_DEATH_TRIGGER_KEYS)
                            if unknown_trigger_keys:
                                errors.append(
                                    f"{trigger_path}: contains unknown keys: {', '.join(unknown_trigger_keys)}"
                                )
                            on_death_effect = trigger.get("on_death")
                            if on_death_effect is not None and (
                                not isinstance(on_death_effect, str)
                                or on_death_effect.strip().lower() not in _VALID_ON_DEATH_EFFECTS
                            ):
                                errors.append(
                                    f"{trigger_path}.on_death: must be one of: "
                                    f"{', '.join(sorted(_VALID_ON_DEATH_EFFECTS))}"
                                )
                            on_death_targets = trigger.get("on_death_targets")
                            if on_death_targets is not None and (
                                not isinstance(on_death_targets, str)
                                or on_death_targets.strip().lower() not in _VALID_ON_DEATH_TARGETS
                            ):
                                errors.append(
                                    f"{trigger_path}.on_death_targets: must be one of: "
                                    f"{', '.join(sorted(_VALID_ON_DEATH_TARGETS))}"
                                )
                            on_death_chance = trigger.get("on_death_chance")
                            if on_death_chance is not None and not isinstance(on_death_chance, (int, float)):
                                errors.append(f"{trigger_path}.on_death_chance: must be a number")
                            always_on_death = trigger.get("always_on_death")
                            if always_on_death is not None and not isinstance(always_on_death, bool):
                                errors.append(f"{trigger_path}.always_on_death: must be a boolean")
                            impact_message = trigger.get("impact_message")
                            if impact_message is not None and not isinstance(impact_message, str):
                                errors.append(f"{trigger_path}.impact_message: must be a string")
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
                invisible_messages = attributes.get("invisible_messages")
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
                        visible=bool(attributes.get("visible", True)),
                        invisible_messages=invisible_messages if isinstance(invisible_messages, list) else None,
                        reveal_chance=float(attributes.get("reveal_chance", 1.0)),
                    )
                )

    logger.info("Finished loading mutations.")
