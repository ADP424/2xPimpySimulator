import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any

import json5
from sqlalchemy import delete, select

from database.models import (
    Breed,
    DogName,
    Event,
    EventAction,
    EventOption,
    EventOutcome,
    Mutation,
    VendorFirstName,
    VendorLastName,
)
from database.models.enums import (
    EVENT_ACTION_TYPE,
    EVENT_SEVERITY,
    EVENT_TARGET_TYPE,
    RARITY,
    SEX,
)
from database.session import session_scope
from logger import get_logger

logger = get_logger("database/load/load_resources")

RESOURCE_ROOT = Path("resources")
BREEDS_ROOT = RESOURCE_ROOT / "breeds"
EVENTS_ROOT = RESOURCE_ROOT / "events"
MUTATIONS_ROOT = RESOURCE_ROOT / "mutations"
DOG_NAMES_ROOT = RESOURCE_ROOT / "dog_names"
VENDOR_NAMES_ROOT = RESOURCE_ROOT / "vendor_names"
VENDOR_FIRST_NAMES_ROOT = VENDOR_NAMES_ROOT / "first"
VENDOR_LAST_NAMES_ROOT = VENDOR_NAMES_ROOT / "last"

_SELECTED_TARGET_TOKEN = "selected"
_RANDOM_TARGET_TOKEN = "random"
_EVENT_ALLOWED_KEYS = {
    "name",
    "description",
    "flavor_text",
    "severity",
    "rarity",
    "requires_response",
    "response_timeout",
    "min_pooches",
    "min_kennels",
    "min_money",
    "min_bloodskulls",
    "triggered_only",
    "advanced_options",
    "actions",
    "options",
}
_OPTION_ALLOWED_KEYS = {
    "label",
    "description",
    "min_money",
    "min_bloodskulls",
    "advanced_options",
    "actions",
    "outcomes",
}
_OUTCOME_ALLOWED_KEYS = {
    "label",
    "description",
    "message",
    "chance",
    "advanced_options",
    "actions",
}
_ACTION_ALLOWED_KEYS = {"action_type", "target_type", "parameters"}
_JSONC_SUFFIXES = {".jsonc", ".json"}


def _enum_values(enum_obj: Any) -> set[str]:
    return {str(value).lower() for value in getattr(enum_obj, "enums", [])}


EVENT_ACTION_VALUES = _enum_values(EVENT_ACTION_TYPE)
EVENT_TARGET_VALUES = _enum_values(EVENT_TARGET_TYPE)
EVENT_SEVERITY_VALUES = _enum_values(EVENT_SEVERITY)
RARITY_VALUES = _enum_values(RARITY)
SEX_VALUES = _enum_values(SEX)


class EventValidationError(ValueError):
    pass


class _EventValidator:
    def __init__(self, breed_names: set[str], mutation_names: set[str], event_names: set[str]):
        self.breed_names = breed_names
        self.mutation_names = mutation_names
        self.event_names = event_names
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def validate_events_json(self, events_json: dict[str, Any]) -> None:
        if not isinstance(events_json, dict):
            self.error("events", "root value must be an object keyed by category")
            return

        for category_name, events in events_json.items():
            category_path = f"events.{category_name}"
            if not isinstance(events, dict):
                self.error(category_path, "category value must be an object keyed by event name")
                continue
            for event_name, attributes in events.items():
                self._validate_event(category_name, event_name, attributes)

    def raise_if_invalid(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise EventValidationError(f"Invalid event resources:\n{joined}")

    def _validate_event(self, category_name: str, event_name: str, attributes: Any) -> None:
        path = f"events.{category_name}.{event_name}"
        if not isinstance(attributes, dict):
            self.error(path, "event definition must be an object")
            return

        self._validate_unknown_keys(path, attributes, _EVENT_ALLOWED_KEYS)

        self._validate_optional_string(path, attributes, "name", allow_blank=False)
        self._validate_optional_string(path, attributes, "description")
        self._validate_optional_string(path, attributes, "flavor_text")
        self._validate_optional_json_object(path, attributes, "advanced_options")
        severity = self._validate_enum_string(path, attributes, "severity", EVENT_SEVERITY_VALUES)
        rarity = self._validate_enum_string(path, attributes, "rarity", RARITY_VALUES)
        requires_response = self._validate_optional_bool(path, attributes, "requires_response")
        response_timeout = self._validate_optional_int(path, attributes, "response_timeout", minimum=1)
        min_pooches = self._validate_optional_int(path, attributes, "min_pooches", minimum=0)
        min_kennels = self._validate_optional_int(path, attributes, "min_kennels", minimum=0)
        min_money = self._validate_optional_int(path, attributes, "min_money", minimum=0)
        min_bloodskulls = self._validate_optional_int(path, attributes, "min_bloodskulls", minimum=0)
        triggered_only = self._validate_optional_bool(path, attributes, "triggered_only")
        actions = self._validate_actions_list(path, attributes.get("actions", []), "actions")
        options = self._validate_options_list(path, attributes.get("options", []))

        if requires_response is True and not options:
            self.error(path, "requires_response=true events must define at least one option")
        if not actions and not options:
            self.error(path, "events must define at least one action or option")

        _ = (
            severity,
            rarity,
            response_timeout,
            min_pooches,
            min_kennels,
            min_money,
            min_bloodskulls,
            triggered_only,
        )

    def _validate_options_list(self, path: str, options: Any) -> list[dict[str, Any]]:
        option_path = f"{path}.options"
        if not isinstance(options, list):
            self.error(option_path, "must be a list")
            return []

        validated: list[dict[str, Any]] = []
        for index, option in enumerate(options):
            current_path = f"{option_path}[{index}]"
            if not isinstance(option, dict):
                self.error(current_path, "option must be an object")
                continue

            self._validate_unknown_keys(current_path, option, _OPTION_ALLOWED_KEYS)
            self._validate_optional_string(current_path, option, "label", allow_blank=False)
            self._validate_optional_string(current_path, option, "description")
            self._validate_optional_int(current_path, option, "min_money", minimum=0)
            self._validate_optional_int(current_path, option, "min_bloodskulls", minimum=0)
            self._validate_optional_json_object(current_path, option, "advanced_options")
            self._validate_actions_list(current_path, option.get("actions", []), "actions")
            self._validate_outcomes_list(current_path, option.get("outcomes", []))
            validated.append(option)

        return validated

    def _validate_outcomes_list(self, path: str, outcomes: Any) -> list[dict[str, Any]]:
        outcomes_path = f"{path}.outcomes"
        if not isinstance(outcomes, list):
            self.error(outcomes_path, "must be a list")
            return []

        validated: list[dict[str, Any]] = []
        for index, outcome in enumerate(outcomes):
            current_path = f"{outcomes_path}[{index}]"
            if not isinstance(outcome, dict):
                self.error(current_path, "outcome must be an object")
                continue

            self._validate_unknown_keys(current_path, outcome, _OUTCOME_ALLOWED_KEYS)
            self._validate_optional_string(current_path, outcome, "label")
            self._validate_optional_string(current_path, outcome, "description")
            self._validate_optional_string(current_path, outcome, "message")
            self._validate_optional_json_object(current_path, outcome, "advanced_options")
            self._validate_optional_probability(current_path, outcome, "chance")
            self._validate_actions_list(current_path, outcome.get("actions", []), "actions")
            validated.append(outcome)

        return validated

    def _validate_actions_list(self, path: str, actions: Any, field_name: str) -> list[dict[str, Any]]:
        actions_path = f"{path}.{field_name}"
        if not isinstance(actions, list):
            self.error(actions_path, "must be a list")
            return []

        validated: list[dict[str, Any]] = []
        for index, action in enumerate(actions):
            current_path = f"{actions_path}[{index}]"
            if not isinstance(action, dict):
                self.error(current_path, "action must be an object")
                continue

            self._validate_unknown_keys(current_path, action, _ACTION_ALLOWED_KEYS)
            action_type = self._validate_enum_string(current_path, action, "action_type", EVENT_ACTION_VALUES)
            target_type = self._validate_enum_string(current_path, action, "target_type", EVENT_TARGET_VALUES)
            parameters = action.get("parameters", {})
            if not isinstance(parameters, dict):
                self.error(f"{current_path}.parameters", "must be an object")
                continue

            if action_type is None or target_type is None:
                continue

            self._validate_action_parameters(current_path, action_type, target_type, parameters)
            validated.append(action)

        return validated

    def _validate_action_parameters(
        self,
        path: str,
        action_type: str,
        target_type: str,
        parameters: dict[str, Any],
    ) -> None:
        params_path = f"{path}.parameters"
        common_allowed = set()

        if target_type == "pooch":
            common_allowed.add("pooch")
            self._validate_entity_selector(params_path, parameters, "pooch")
        if target_type == "kennel":
            common_allowed.add("kennel")
            self._validate_entity_selector(params_path, parameters, "kennel")

        if action_type in {"modify_money", "modify_bloodskulls"}:
            self._validate_allowed_keys(
                params_path, parameters, common_allowed | {"amount", "min_amount", "max_amount"}
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_target_type(path, action_type, target_type, {"owner"})

        elif action_type in {"modify_pooch_health", "modify_pooch_age"}:
            self._validate_allowed_keys(
                params_path, parameters, common_allowed | {"amount", "min_amount", "max_amount"}
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type == "kill_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type in {"add_mutation", "remove_mutation"}:
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"mutation"})
            self._validate_optional_known_name(params_path, parameters, "mutation", self.mutation_names)
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type == "add_breed":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"breed", "weight"})
            self._validate_optional_known_name(params_path, parameters, "breed", self.breed_names)
            self._validate_optional_number(params_path, parameters, "weight", minimum_exclusive=0)
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type == "transfer_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"new_owner_discord_id", "vendor_id"})
            self._validate_requires_one_of(params_path, parameters, [("new_owner_discord_id",), ("vendor_id",)])
            self._validate_mutually_exclusive(params_path, parameters, "new_owner_discord_id", "vendor_id")
            self._validate_optional_int(params_path, parameters, "new_owner_discord_id", minimum=1)
            self._validate_optional_int(params_path, parameters, "vendor_id", minimum=1)
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type == "create_pooch":
            self._validate_allowed_keys(
                params_path,
                parameters,
                {
                    "name",
                    "sex",
                    "age",
                    "base_health",
                    "breeding_cooldown",
                },
            )
            self._validate_optional_string(params_path, parameters, "name", allow_blank=False)
            self._validate_enum_string(params_path, parameters, "sex", SEX_VALUES)
            self._validate_optional_int(params_path, parameters, "age", minimum=0)
            self._validate_optional_int(params_path, parameters, "base_health")
            self._validate_optional_int(params_path, parameters, "breeding_cooldown", minimum=0)
            self._validate_target_type(path, action_type, target_type, {"owner"})

        elif action_type == "modify_kennel_capacity":
            self._validate_allowed_keys(
                params_path, parameters, common_allowed | {"amount", "min_amount", "max_amount"}
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_target_type(path, action_type, target_type, {"kennel", "all_kennels"})

        elif action_type == "rename_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"name"})
            self._validate_optional_string(params_path, parameters, "name", allow_blank=False)
            self._validate_requires_one_of(params_path, parameters, [("name",)])
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type == "set_breeding_cooldown":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"cooldown"})
            self._validate_optional_int(params_path, parameters, "cooldown", minimum=0)
            self._validate_requires_one_of(params_path, parameters, [("cooldown",)])
            self._validate_target_type(path, action_type, target_type, {"pooch", "all_pooches"})

        elif action_type == "start_event":
            self._validate_allowed_keys(params_path, parameters, {"event", "random_event"})
            event_name = self._validate_optional_known_name(params_path, parameters, "event", self.event_names)
            random_event = self._validate_optional_bool(params_path, parameters, "random_event")
            if random_event is not True and event_name is None:
                self.error(params_path, "requires 'event' unless 'random_event' is true")
            self._validate_target_type(path, action_type, target_type, {"owner"})

        else:
            self.error(path, f"unsupported action type '{action_type}'")

    def _validate_unknown_keys(self, path: str, value: dict[str, Any], allowed_keys: set[str]) -> None:
        self._validate_allowed_keys(path, value, allowed_keys)

    def _validate_allowed_keys(self, path: str, value: dict[str, Any], allowed_keys: set[str]) -> None:
        unknown = sorted(set(value) - allowed_keys)
        if unknown:
            self.error(path, f"contains unknown keys: {', '.join(unknown)}")

    def _validate_target_type(self, path: str, action_type: str, target_type: str, allowed: set[str]) -> None:
        if target_type not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            self.error(path, f"action_type '{action_type}' only supports target_type values: {allowed_text}")

    def _validate_requires_one_of(
        self,
        path: str,
        value: dict[str, Any],
        groups: list[tuple[str, ...]],
    ) -> None:
        if any(all(field in value for field in group) for group in groups):
            return
        rendered = [" + ".join(group) for group in groups]
        self.error(path, f"requires at least one of: {'; '.join(rendered)}")

    def _validate_mutually_exclusive(self, path: str, value: dict[str, Any], left: str, right: str) -> None:
        if left in value and right in value:
            self.error(path, f"'{left}' and '{right}' cannot both be present")

    def _validate_amount_group(self, path: str, value: dict[str, Any]) -> None:
        amount_present = "amount" in value
        min_present = "min_amount" in value
        max_present = "max_amount" in value

        self._validate_optional_int(path, value, "amount")
        min_amount = self._validate_optional_int(path, value, "min_amount")
        max_amount = self._validate_optional_int(path, value, "max_amount")

        if amount_present and (min_present or max_present):
            self.error(path, "cannot mix 'amount' with 'min_amount'/'max_amount'")
        if min_present != max_present:
            self.error(path, "'min_amount' and 'max_amount' must either both be present or both be omitted")
        if min_amount is not None and max_amount is not None and min_amount > max_amount:
            self.error(path, "'min_amount' cannot be greater than 'max_amount'")

    def _validate_entity_selector(self, path: str, value: dict[str, Any], field_name: str) -> int | str | None:
        if field_name not in value:
            self.error(path, f"requires '{field_name}' for this target_type")
            return None
        raw_value = value[field_name]
        if isinstance(raw_value, bool):
            self.error(f"{path}.{field_name}", "must be 'selected' or 'random'")
            return None
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in {_SELECTED_TARGET_TOKEN, _RANDOM_TARGET_TOKEN}:
                return normalized
        self.error(f"{path}.{field_name}", "must be 'selected' or 'random'")
        return None

    def _validate_optional_known_name(
        self,
        path: str,
        value: dict[str, Any],
        field_name: str,
        valid_names: set[str],
    ) -> str | None:
        raw_value = self._validate_optional_string(path, value, field_name, allow_blank=False)
        if raw_value is None:
            return None
        normalized_value = raw_value.strip().lower()
        if normalized_value not in valid_names:
            self.error(f"{path}.{field_name}", "references a name that does not exist")
        return normalized_value

    def _validate_optional_string(
        self,
        path: str,
        value: dict[str, Any],
        field_name: str,
        *,
        allow_blank: bool = True,
    ) -> str | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if not isinstance(raw_value, str):
            self.error(f"{path}.{field_name}", "must be a string")
            return None
        if not allow_blank and not raw_value.strip():
            self.error(f"{path}.{field_name}", "must not be blank")
            return None
        return raw_value

    def _validate_optional_json_object(
        self, path: str, value: dict[str, Any], field_name: str
    ) -> dict[str, Any] | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if not isinstance(raw_value, dict):
            self.error(f"{path}.{field_name}", "must be an object")
            return None
        return raw_value

    def _validate_optional_bool(self, path: str, value: dict[str, Any], field_name: str) -> bool | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if not isinstance(raw_value, bool):
            self.error(f"{path}.{field_name}", "must be a boolean")
            return None
        return raw_value

    def _validate_optional_int(
        self,
        path: str,
        value: dict[str, Any],
        field_name: str,
        minimum: int | None = None,
    ) -> int | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            self.error(f"{path}.{field_name}", "must be an integer")
            return None
        if minimum is not None and raw_value < minimum:
            self.error(f"{path}.{field_name}", f"must be at least {minimum}")
            return None
        return raw_value

    def _validate_optional_number(
        self,
        path: str,
        value: dict[str, Any],
        field_name: str,
        *,
        minimum_exclusive: float | None = None,
    ) -> float | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            self.error(f"{path}.{field_name}", "must be a number")
            return None
        numeric_value = float(raw_value)
        if minimum_exclusive is not None and numeric_value <= minimum_exclusive:
            self.error(f"{path}.{field_name}", f"must be greater than {minimum_exclusive}")
            return None
        return numeric_value

    def _validate_optional_probability(self, path: str, value: dict[str, Any], field_name: str) -> float | None:
        if field_name not in value:
            return None
        numeric_value = self._validate_optional_number(path, value, field_name)
        if numeric_value is None:
            return None
        if numeric_value < 0 or numeric_value > 1:
            self.error(f"{path}.{field_name}", "must be between 0 and 1")
            return None
        return numeric_value

    def _validate_enum_string(
        self,
        path: str,
        value: dict[str, Any],
        field_name: str,
        valid_values: set[str],
    ) -> str | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if not isinstance(raw_value, str):
            self.error(f"{path}.{field_name}", "must be a string")
            return None
        normalized = raw_value.strip().lower()
        if normalized not in valid_values:
            self.error(
                f"{path}.{field_name}",
                f"must be one of: {', '.join(sorted(valid_values))}",
            )
            return None
        return normalized


def _titleize_slug(value: str) -> str:
    normalized = value.replace("-", "_").strip("_")
    parts = [part for part in normalized.split("_") if part]
    return " ".join(part.capitalize() for part in parts) or value


def _iter_files(root: Path, suffixes: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def _load_jsonc_file(path: Path) -> dict[str, Any]:
    payload = json5.loads(path.read_text(encoding="utf8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected an object in {path}")
    return payload


def _load_names_from_root(root: Path) -> list[str]:
    names: list[str] = []
    for path in _iter_files(root, {".txt"}):
        for raw_name in path.read_text(encoding="utf8").splitlines():
            name = raw_name.strip()
            if name:
                names.append(name)
    return names


def _load_categorized_resource_objects(root: Path, label: str) -> dict[str, dict[str, dict[str, Any]]]:
    resources: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    seen_names: dict[str, Path] = {}

    for path in _iter_files(root, _JSONC_SUFFIXES):
        relative = path.relative_to(root)
        if len(relative.parts) < 2:
            raise ValueError(f"{label} file must live inside a category folder: {path}")

        category = _titleize_slug(relative.parts[0])
        payload = _load_jsonc_file(path)
        name = str(payload.get("name") or _titleize_slug(path.stem)).strip()
        if not name:
            raise ValueError(f"{label} file has a blank name: {path}")

        if name in seen_names:
            raise ValueError(f"Duplicate {label} name '{name}' in {seen_names[name]} and {path}")
        seen_names[name] = path

        payload = dict(payload)
        payload.pop("name", None)
        resources[category][name] = payload

    return {category: items for category, items in resources.items()}


def _resolve_event_action_parameters(
    parameters: dict[str, Any],
    breed_name_to_id: dict[str, int],
    mutation_name_to_id: dict[str, int],
) -> dict[str, Any]:
    resolved = dict(parameters)

    mutation_name = resolved.pop("mutation", None)
    if isinstance(mutation_name, str):
        mutation_id = mutation_name_to_id.get(mutation_name.strip().lower())
        if mutation_id is not None:
            resolved["mutation_id"] = mutation_id

    breed_name = resolved.pop("breed", None)
    if isinstance(breed_name, str):
        breed_id = breed_name_to_id.get(breed_name.strip().lower())
        if breed_id is not None:
            resolved["breed_id"] = breed_id

    return resolved


async def load_breeds():
    logger.info("Loading breeds from 'resources/breeds/**/*.jsonc' into the database...")

    breeds_json = _load_categorized_resource_objects(BREEDS_ROOT, "breed")

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


async def load_mutations():
    logger.info("Loading mutations from 'resources/mutations/**/*.jsonc' into the database...")

    mutations_json = _load_categorized_resource_objects(MUTATIONS_ROOT, "mutation")

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
                        advanced_options=attributes.get("advanced_options", {}),
                    )
                )

    logger.info("Finished loading mutations.")


async def load_dog_names():
    logger.info("Loading dog names from 'resources/dog_names/**/*.txt' into the database...")

    dog_names = _load_names_from_root(DOG_NAMES_ROOT)

    async with session_scope() as session:
        await session.execute(delete(DogName))

        for dog_name in dog_names:
            session.add(DogName(name=dog_name))

    logger.info("Finished loading dog names.")


async def load_vendor_first_names():
    logger.info("Loading vendor first names from 'resources/vendor_names/first/**/*.txt' into the database...")

    vendor_first_names = _load_names_from_root(VENDOR_FIRST_NAMES_ROOT)

    async with session_scope() as session:
        await session.execute(delete(VendorFirstName))

        for vendor_first_name in vendor_first_names:
            session.add(VendorFirstName(name=vendor_first_name))

    logger.info("Finished loading vendor first names.")


async def load_vendor_last_names():
    logger.info("Loading vendor last names from 'resources/vendor_names/last/**/*.txt' into the database...")

    vendor_last_names = _load_names_from_root(VENDOR_LAST_NAMES_ROOT)

    async with session_scope() as session:
        await session.execute(delete(VendorLastName))

        for vendor_last_name in vendor_last_names:
            session.add(VendorLastName(name=vendor_last_name))

    logger.info("Finished loading vendor last names.")


async def load_events():
    logger.info("Loading events from 'resources/events/**/*.jsonc' into the database...")

    events_json = _load_categorized_resource_objects(EVENTS_ROOT, "event")
    event_names = {event_name.strip().lower() for events in events_json.values() for event_name in events}

    async with session_scope() as session:
        breed_names = {name.strip().lower() for name in (await session.execute(select(Breed.name))).scalars().all()}
        mutation_names = {
            name.strip().lower() for name in (await session.execute(select(Mutation.name))).scalars().all()
        }
        breed_name_to_id = {
            breed.name.strip().lower(): breed.id for breed in (await session.execute(select(Breed))).scalars().all()
        }
        mutation_name_to_id = {
            mutation.name.strip().lower(): mutation.id
            for mutation in (await session.execute(select(Mutation))).scalars().all()
        }

        validator = _EventValidator(
            breed_names=breed_names,
            mutation_names=mutation_names,
            event_names=event_names,
        )
        validator.validate_events_json(events_json)
        validator.raise_if_invalid()

        await session.execute(delete(EventAction))
        await session.execute(delete(EventOutcome))
        await session.execute(delete(EventOption))
        await session.execute(delete(Event))

        for event_category, events in events_json.items():
            for event_name, attributes in events.items():
                event = Event(
                    name=str(event_name),
                    category=str(event_category),
                    description=str(attributes.get("description", f"{event_name} is a random event that can occur.")),
                    flavor_text=str(attributes.get("flavor_text", "")),
                    severity=str(attributes.get("severity", "minor")).lower(),
                    rarity=str(attributes.get("rarity", "common")).lower(),
                    requires_response=bool(attributes.get("requires_response", False)),
                    response_timeout=int(attributes.get("response_timeout", 3600)),
                    min_pooches=int(attributes.get("min_pooches", 0)),
                    min_kennels=int(attributes.get("min_kennels", 0)),
                    min_money=int(attributes.get("min_money", 0)),
                    min_bloodskulls=int(attributes.get("min_bloodskulls", 0)),
                    triggered_only=bool(attributes.get("triggered_only", False)),
                    advanced_options=attributes.get("advanced_options", {}),
                )
                session.add(event)
                await session.flush()

                for idx, action_data in enumerate(attributes.get("actions", [])):
                    action = EventAction(
                        event_id=event.id,
                        action_order=idx,
                        action_type=str(action_data.get("action_type")).lower(),
                        target_type=str(action_data.get("target_type", "owner")).lower(),
                        parameters=_resolve_event_action_parameters(
                            action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                        ),
                    )
                    session.add(action)

                for opt_idx, option_data in enumerate(attributes.get("options", [])):
                    option = EventOption(
                        event_id=event.id,
                        option_order=opt_idx,
                        label=str(option_data.get("label", f"Option {opt_idx + 1}")),
                        description=str(option_data.get("description", "")),
                        min_money=int(option_data.get("min_money", 0)),
                        min_bloodskulls=int(option_data.get("min_bloodskulls", 0)),
                        advanced_options=option_data.get("advanced_options", {}),
                    )
                    session.add(option)
                    await session.flush()

                    for act_idx, opt_action_data in enumerate(option_data.get("actions", [])):
                        option_action = EventAction(
                            option_id=option.id,
                            action_order=act_idx,
                            action_type=str(opt_action_data.get("action_type")).lower(),
                            target_type=str(opt_action_data.get("target_type", "owner")).lower(),
                            parameters=_resolve_event_action_parameters(
                                opt_action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                            ),
                        )
                        session.add(option_action)

                    for outcome_idx, outcome_data in enumerate(option_data.get("outcomes", [])):
                        outcome = EventOutcome(
                            option_id=option.id,
                            outcome_order=outcome_idx,
                            label=str(outcome_data.get("label", "")),
                            description=str(outcome_data.get("description", "")),
                            message=str(outcome_data.get("message", "")),
                            chance=float(outcome_data["chance"]) if "chance" in outcome_data else None,
                            advanced_options=outcome_data.get("advanced_options", {}),
                        )
                        session.add(outcome)
                        await session.flush()

                        for outcome_action_idx, outcome_action_data in enumerate(outcome_data.get("actions", [])):
                            outcome_action = EventAction(
                                outcome_id=outcome.id,
                                action_order=outcome_action_idx,
                                action_type=str(outcome_action_data.get("action_type")).lower(),
                                target_type=str(outcome_action_data.get("target_type", "owner")).lower(),
                                parameters=_resolve_event_action_parameters(
                                    outcome_action_data.get("parameters", {}),
                                    breed_name_to_id,
                                    mutation_name_to_id,
                                ),
                            )
                            session.add(outcome_action)

    logger.info("Finished loading events.")


async def main():
    logger.info("Loading resources into database...")

    await load_breeds()
    await load_mutations()
    await load_dog_names()
    await load_vendor_first_names()
    await load_vendor_last_names()
    await load_events()

    logger.info("Finished loading resources into database.")


if __name__ == "__main__":
    asyncio.run(main())
