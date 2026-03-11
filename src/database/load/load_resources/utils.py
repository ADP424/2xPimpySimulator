from collections import defaultdict
from pathlib import Path
from typing import Any

import json5

from logger import get_logger

from ...models import (
    EVENT_ACTION_TYPE,
    EVENT_SEVERITY,
    EVENT_TARGET_TYPE,
    HEALTH_IMPACT,
    RARITY,
    SEX,
)

logger = get_logger("database/load/load_resources")

RESOURCE_ROOT = Path("resources")
VENDOR_NAMES_ROOT = RESOURCE_ROOT / "vendor_names"

_SELECTED_TARGET_TOKEN = "selected"
_RANDOM_TARGET_TOKEN = "random"
_JSONC_SUFFIXES = {".jsonc", ".json"}

_ACTION_ALLOWED_KEYS = {"action_type", "target_type", "parameters"}

_OWNER_FILTER_ALLOWED_KEYS = {
    "min_money",
    "max_money",
    "min_bloodskulls",
    "max_bloodskulls",
    "min_pooches",
    "max_pooches",
    "min_kennels",
    "max_kennels",
    "kennels",
    "pooches",
}
_KENNEL_FILTER_ALLOWED_KEYS = {
    "min_count",
    "max_count",
    "description",
    "min_capacity",
    "max_capacity",
    "min_pooches",
    "max_pooches",
    "pooches",
}
_POOCH_FILTER_ALLOWED_KEYS = {
    "min_count",
    "max_count",
    "description",
    "min_age",
    "max_age",
    "sex",
    "min_health",
    "max_health",
    "is_virgin",
    "is_alive",
    "min_breeding_cooldown",
    "max_breeding_cooldown",
    "has_any_breed",
    "has_all_breeds",
    "exclude_breeds",
    "has_any_mutation",
    "has_all_mutations",
    "exclude_mutations",
    "location",
}


def _enum_values(enum_obj: Any) -> set[str]:
    return {str(value).lower() for value in getattr(enum_obj, "enums", [])}


EVENT_ACTION_VALUES = _enum_values(EVENT_ACTION_TYPE)
EVENT_TARGET_VALUES = _enum_values(EVENT_TARGET_TYPE)
EVENT_SEVERITY_VALUES = _enum_values(EVENT_SEVERITY)
HEALTH_IMPACT_VALUES = _enum_values(HEALTH_IMPACT)
RARITY_VALUES = _enum_values(RARITY)
SEX_VALUES = _enum_values(SEX)
LOCATION_VALUES = {"kennel", "homeless", "any"}


class EventValidationError(ValueError):
    pass


class ResourceValidationError(ValueError):
    pass


def validate_name_list(resource_name: str, names: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    validated: list[str] = []
    for index, name in enumerate(names):
        if not isinstance(name, str):
            errors.append(f"{resource_name}[{index}]: must be a string")
            continue
        normalized = name.strip()
        if not normalized:
            errors.append(f"{resource_name}[{index}]: must not be blank")
            continue
        lowered = normalized.lower()
        if lowered in seen:
            errors.append(f"{resource_name}[{index}]: duplicate name '{normalized}' also found as '{seen[lowered]}'")
            continue
        seen[lowered] = normalized
        validated.append(normalized)
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ResourceValidationError(f"Invalid {resource_name} resources:\n{joined}")
    return validated


def _iter_files(root: Path, suffixes: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def load_names_from_root(root: Path) -> list[str]:
    names: list[str] = []
    for path in _iter_files(root, {".txt"}):
        for raw_name in path.read_text(encoding="utf8").splitlines():
            name = raw_name.strip()
            if name:
                names.append(name)
    return names


def load_categorized_resource_objects(root: Path, label: str) -> dict[str, dict[str, dict[str, Any]]]:

    def _titleize_slug(value: str) -> str:
        normalized = value.replace("-", "_").strip("_")
        parts = [part for part in normalized.split("_") if part]
        return " ".join(part.capitalize() for part in parts) or value

    def _load_jsonc_file(path: Path) -> dict[str, Any]:
        payload = json5.loads(path.read_text(encoding="utf8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected an object in {path}")
        return payload

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


def resolve_event_action_parameters(
    parameters: dict[str, Any],
    breed_name_to_id: dict[str, int],
    mutation_name_to_id: dict[str, int],
) -> dict[str, Any]:
    resolved = dict(parameters)

    mutation_name = resolved.get("mutation")
    if isinstance(mutation_name, str):
        mutation_id = mutation_name_to_id.get(mutation_name.strip().lower())
        if mutation_id is not None:
            resolved["mutation_id"] = mutation_id

    breed_name = resolved.get("breed")
    if isinstance(breed_name, str):
        breed_id = breed_name_to_id.get(breed_name.strip().lower())
        if breed_id is not None:
            resolved["breed_id"] = breed_id

    return resolved


class BaseEventValidator:
    def __init__(self, breed_names: set[str], mutation_names: set[str], event_names: set[str]):
        self.breed_names = breed_names
        self.mutation_names = mutation_names
        self.event_names = event_names
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def raise_if_invalid(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise EventValidationError(f"Invalid event resources:\n{joined}")

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
        common_allowed: set[str] = set()

        if target_type == "pooch":
            common_allowed |= {"pooch", "filter"}
            self._validate_entity_selector(params_path, parameters, "pooch")
            if "filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.filter",
                    parameters["filter"],
                    allow_counts=False,
                    allow_location=True,
                )
        elif target_type == "all_pooches":
            common_allowed |= {"filter"}
            if "filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.filter",
                    parameters["filter"],
                    allow_counts=False,
                    allow_location=True,
                )
        elif target_type == "kennel":
            common_allowed |= {"kennel", "filter"}
            self._validate_entity_selector(params_path, parameters, "kennel")
            if "filter" in parameters:
                self._validate_kennel_filter(f"{params_path}.filter", parameters["filter"], allow_counts=False)
        elif target_type == "all_kennels":
            common_allowed |= {"filter"}
            if "filter" in parameters:
                self._validate_kennel_filter(f"{params_path}.filter", parameters["filter"], allow_counts=False)

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
            self._validate_cooldown_value(params_path, parameters, "cooldown")
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

    def _validate_kennel_filter(self, path: str, filter_data: Any, *, allow_counts: bool) -> None:
        if not isinstance(filter_data, dict):
            self.error(path, "must be an object")
            return

        allowed_keys = set(_KENNEL_FILTER_ALLOWED_KEYS)
        if not allow_counts:
            allowed_keys -= {"min_count", "max_count", "description"}

        self._validate_unknown_keys(path, filter_data, allowed_keys)

        if allow_counts:
            self._validate_min_max_pair(path, filter_data, "min_count", "max_count", minimum=0)
            self._validate_optional_string(path, filter_data, "description")

        self._validate_min_max_pair(path, filter_data, "min_capacity", "max_capacity", minimum=0)
        self._validate_min_max_pair(path, filter_data, "min_pooches", "max_pooches", minimum=0)

        pooches = filter_data.get("pooches", [])
        if not isinstance(pooches, list):
            self.error(f"{path}.pooches", "must be a list")
        else:
            for idx, pooch_filter in enumerate(pooches):
                self._validate_pooch_filter(
                    f"{path}.pooches[{idx}]",
                    pooch_filter,
                    allow_counts=True,
                    allow_location=False,
                )

    def _validate_pooch_filter(
        self,
        path: str,
        filter_data: Any,
        *,
        allow_counts: bool,
        allow_location: bool,
    ) -> None:
        if not isinstance(filter_data, dict):
            self.error(path, "must be an object")
            return

        allowed_keys = set(_POOCH_FILTER_ALLOWED_KEYS)
        if not allow_counts:
            allowed_keys -= {"min_count", "max_count", "description"}
        if not allow_location:
            allowed_keys.discard("location")

        self._validate_unknown_keys(path, filter_data, allowed_keys)

        if allow_counts:
            self._validate_min_max_pair(path, filter_data, "min_count", "max_count", minimum=0)
            self._validate_optional_string(path, filter_data, "description")

        self._validate_min_max_pair(path, filter_data, "min_age", "max_age", minimum=0)
        self._validate_enum_string(path, filter_data, "sex", SEX_VALUES)
        self._validate_min_max_pair(path, filter_data, "min_health", "max_health")
        self._validate_optional_bool(path, filter_data, "is_virgin")
        self._validate_optional_bool(path, filter_data, "is_alive")
        self._validate_min_max_pair(
            path,
            filter_data,
            "min_breeding_cooldown",
            "max_breeding_cooldown",
            minimum=0,
        )

        self._validate_name_list(path, filter_data, "has_any_breed", self.breed_names)
        self._validate_name_list(path, filter_data, "has_all_breeds", self.breed_names)
        self._validate_name_list(path, filter_data, "exclude_breeds", self.breed_names)
        self._validate_name_list(path, filter_data, "has_any_mutation", self.mutation_names)
        self._validate_name_list(path, filter_data, "has_all_mutations", self.mutation_names)
        self._validate_name_list(path, filter_data, "exclude_mutations", self.mutation_names)

        if allow_location:
            self._validate_enum_string(path, filter_data, "location", LOCATION_VALUES)

    def _validate_owner_filter(self, path: str, filter_data: Any) -> None:
        if filter_data is None:
            return
        if not isinstance(filter_data, dict):
            self.error(path, "must be an object")
            return

        if not filter_data:
            return

        self._validate_unknown_keys(path, filter_data, _OWNER_FILTER_ALLOWED_KEYS)

        self._validate_min_max_pair(path, filter_data, "min_money", "max_money", minimum=0)
        self._validate_min_max_pair(path, filter_data, "min_bloodskulls", "max_bloodskulls", minimum=0)
        self._validate_min_max_pair(path, filter_data, "min_pooches", "max_pooches", minimum=0)
        self._validate_min_max_pair(path, filter_data, "min_kennels", "max_kennels", minimum=0)

        kennels = filter_data.get("kennels", [])
        if not isinstance(kennels, list):
            self.error(f"{path}.kennels", "must be a list")
        else:
            for idx, kennel_filter in enumerate(kennels):
                self._validate_kennel_filter(f"{path}.kennels[{idx}]", kennel_filter, allow_counts=True)

        pooches = filter_data.get("pooches", [])
        if not isinstance(pooches, list):
            self.error(f"{path}.pooches", "must be a list")
        else:
            for idx, pooch_filter in enumerate(pooches):
                self._validate_pooch_filter(
                    f"{path}.pooches[{idx}]",
                    pooch_filter,
                    allow_counts=True,
                    allow_location=True,
                )

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

    def _validate_min_max_pair(
        self,
        path: str,
        value: dict[str, Any],
        min_field_name: str,
        max_field_name: str,
        *,
        minimum: int | None = None,
    ) -> tuple[int | None, int | None]:
        min_value = self._validate_optional_int(path, value, min_field_name, minimum=minimum)
        max_value = self._validate_optional_int(path, value, max_field_name, minimum=minimum)
        if min_value is not None and max_value is not None and min_value > max_value:
            self.error(path, f"'{min_field_name}' cannot be greater than '{max_field_name}'")
        return min_value, max_value

    def _validate_entity_selector(self, path: str, value: dict[str, Any], field_name: str) -> str | None:
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

    def _validate_name_list(
        self,
        path: str,
        value: dict[str, Any],
        field_name: str,
        valid_names: set[str],
    ) -> list[str] | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if not isinstance(raw_value, list):
            self.error(f"{path}.{field_name}", "must be a list of strings")
            return None

        validated: list[str] = []
        for idx, item in enumerate(raw_value):
            if not isinstance(item, str):
                self.error(f"{path}.{field_name}[{idx}]", "must be a string")
                continue
            normalized = item.strip().lower()
            if normalized not in valid_names:
                self.error(f"{path}.{field_name}[{idx}]", f"references unknown name '{item}'")
            else:
                validated.append(normalized)

        return validated

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

    def _validate_cooldown_value(self, path: str, value: dict[str, Any], field_name: str) -> None:
        if field_name not in value:
            return
        raw_value = value[field_name]
        if isinstance(raw_value, str):
            if raw_value.strip().lower() != "base":
                self.error(f"{path}.{field_name}", "string value must be 'base'")
        elif isinstance(raw_value, bool) or not isinstance(raw_value, int):
            self.error(f"{path}.{field_name}", "must be an integer or 'base'")
        elif raw_value < 0:
            self.error(f"{path}.{field_name}", "must be at least 0")
