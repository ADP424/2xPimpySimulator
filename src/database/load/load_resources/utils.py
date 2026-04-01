from collections import defaultdict
from pathlib import Path
from typing import Any

import json5

from src.logger import get_logger

from ...models import (
    EVENT_SEVERITY,
    HEALTH_IMPACT,
    RARITY,
    SEX,
)
from ...models.enums import EVENT_ACTION_TYPE, EVENT_TARGET_TYPE

logger = get_logger("database/load/load_resources")

RESOURCE_ROOT = Path("resources")
VENDOR_NAMES_ROOT = RESOURCE_ROOT / "vendor_names"

_SELECTOR_TOKENS = {"selected", "random", "all", "random_exclude", "all_exclude"}
_JSONC_SUFFIXES = {".jsonc", ".json"}

_ACTION_ALLOWED_KEYS = {"action_type", "target_type", "parameters", "repeat"}

_OWNER_FILTER_ALLOWED_KEYS = {
    "seasons",
    "min_money",
    "max_money",
    "exclude_money",
    "min_bloodskulls",
    "max_bloodskulls",
    "exclude_bloodskulls",
    "min_pooches",
    "max_pooches",
    "exclude_pooches",
    "min_kennels",
    "max_kennels",
    "exclude_kennels",
    "kennels",
    "pooches",
    "graveyard_pooches",
    "hell_pooches",
}

# Used for per-owner sub-filter inside ServerEventFilterSpec.owners
_OWNER_SUBFILTER_ALLOWED_KEYS = _OWNER_FILTER_ALLOWED_KEYS | {"min_count", "max_count"}
_KENNEL_FILTER_ALLOWED_KEYS = {
    "min_count",
    "max_count",
    "description",
    "min_capacity",
    "max_capacity",
    "exclude_capacity",
    "min_upgrade_tier",
    "max_upgrade_tier",
    "exclude_upgrade_tier",
    "min_pooches",
    "max_pooches",
    "exclude_pooches",
    "at_capacity",
    "pooches",
}
_POOCH_FILTER_ALLOWED_KEYS = {
    "min_count",
    "max_count",
    "description",
    "min_age",
    "max_age",
    "exclude_age",
    "sex",
    "min_health",
    "max_health",
    "exclude_health",
    "is_virgin",
    "is_alive",
    "min_breeding_cooldown",
    "max_breeding_cooldown",
    "exclude_breeding_cooldown",
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
LOCATION_VALUES = {"kennel", "graveyard", "hell", "town", "all", "any"}


class EventValidationError(ValueError):
    pass


class ResourceValidationError(ValueError):
    pass


def validate_name_list(resource_name: str, names: list[str]) -> list[str]:
    """
    Validate name list.

    Parameters
    ----------
    resource_name: Any
        The `resource_name` value.

    names: Any
        The `names` value.

    Returns
    -------
    Any
        The result of calling `validate_name_list`.
    """

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


def iter_files(root: Path, suffixes: set[str]) -> list[Path]:
    """
    Iter files.

    Parameters
    ----------
    root: Any
        The `root` value.

    suffixes: Any
        The `suffixes` value.

    Returns
    -------
    Any
        The result of calling `iter_files`.
    """

    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def load_names_from_root(root: Path) -> list[str]:
    """
    Load names from root.

    Parameters
    ----------
    root: Any
        The `root` value.

    Returns
    -------
    Any
        The result of calling `load_names_from_root`.
    """

    names: list[str] = []
    for path in iter_files(root, {".txt"}):
        for raw_name in path.read_text(encoding="utf8").splitlines():
            name = raw_name.strip()
            if name:
                names.append(name)
    return names


def load_categorized_resource_objects(root: Path, label: str) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Load categorized resource objects.

    Parameters
    ----------
    root: Any
        The `root` value.

    label: Any
        The `label` value.

    Returns
    -------
    Any
        The result of calling `load_categorized_resource_objects`.
    """

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

    for path in iter_files(root, _JSONC_SUFFIXES):
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
    """
    Resolve event action parameters.

    Parameters
    ----------
    parameters: Any
        The `parameters` value.

    breed_name_to_id: Any
        The `breed_name_to_id` value.

    mutation_name_to_id: Any
        The `mutation_name_to_id` value.

    Returns
    -------
    Any
        The result of calling `resolve_event_action_parameters`.
    """

    resolved = dict(parameters)

    mutation_name = resolved.get("mutation")
    if isinstance(mutation_name, str):
        mutation_id = mutation_name_to_id.get(mutation_name.strip().lower())
        if mutation_id is not None:
            resolved["mutation_id"] = mutation_id

    # Resolve a list of mutation names to IDs
    mutations_list = resolved.get("mutations")
    if isinstance(mutations_list, list):
        resolved_mutation_ids = []
        for m in mutations_list:
            if isinstance(m, str):
                mid = mutation_name_to_id.get(m.strip().lower())
                if mid is not None:
                    resolved_mutation_ids.append(mid)
        resolved["mutation_ids"] = resolved_mutation_ids

    breed_name = resolved.get("breed")
    if isinstance(breed_name, str):
        breed_id = breed_name_to_id.get(breed_name.strip().lower())
        if breed_id is not None:
            resolved["breed_id"] = breed_id

    return resolved


class BaseEventValidator:
    def __init__(
        self,
        breed_names: set[str],
        mutation_names: set[str],
        event_names: set[str],
        injury_names: set[str] | None = None,
    ):
        self.breed_names = breed_names
        self.mutation_names = mutation_names
        self.event_names = event_names
        self.injury_names: set[str] = injury_names or set()
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
            repeat = self._validate_optional_int(current_path, action, "repeat", minimum=1)
            if repeat is not None and repeat < 1:
                self.error(f"{current_path}.repeat", "must be at least 1")
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
            common_allowed |= {
                "selector",
                "count",
                "filter",
                "save_as",
                "save_kennel",
                "save_owner",
                "use_saved",
                "exclude_claimed",
            }
            if "use_saved" not in parameters:
                self._validate_entity_selector(params_path, parameters, "selector")
            else:
                self._validate_optional_string(params_path, parameters, "use_saved", allow_blank=False)
                if "selector" in parameters:
                    self.error(params_path, "'selector' and 'use_saved' cannot both be present")
            self._validate_optional_int(params_path, parameters, "count", minimum=1)
            if "filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.filter",
                    parameters["filter"],
                    allow_counts=False,
                    allow_location=True,
                )
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            self._validate_optional_bool(params_path, parameters, "save_kennel")
            self._validate_optional_bool(params_path, parameters, "save_owner")
            self._validate_optional_bool(params_path, parameters, "exclude_claimed")
        elif target_type == "kennel":
            common_allowed |= {
                "selector",
                "count",
                "filter",
                "pooch_filter",
                "pooch_selector",
                "pooch_count",
                "save_as",
                "save_excluded_as",
                "use_saved",
            }
            if "use_saved" not in parameters:
                self._validate_entity_selector(params_path, parameters, "selector")
            else:
                self._validate_optional_string(params_path, parameters, "use_saved", allow_blank=False)
                if "selector" in parameters:
                    self.error(params_path, "'selector' and 'use_saved' cannot both be present")
            self._validate_optional_int(params_path, parameters, "count", minimum=1)
            if "filter" in parameters:
                self._validate_kennel_filter(f"{params_path}.filter", parameters["filter"], allow_counts=False)
            if "pooch_filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.pooch_filter",
                    parameters["pooch_filter"],
                    allow_counts=False,
                    allow_location=True,
                )
            if "pooch_selector" in parameters:
                raw_ps = parameters["pooch_selector"]
                if not isinstance(raw_ps, str) or raw_ps.strip().lower() not in {"random", "random_exclude", "all"}:
                    self.error(params_path, "'pooch_selector' must be 'random', 'random_exclude', or 'all'")
            self._validate_optional_int(params_path, parameters, "pooch_count", minimum=1)
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            self._validate_optional_string(params_path, parameters, "save_excluded_as", allow_blank=False)
            if "save_excluded_as" in parameters and parameters.get("pooch_selector") != "random_exclude":
                self.error(params_path, "'save_excluded_as' requires 'pooch_selector': 'random_exclude'")
        elif target_type == "owner":
            # Pooch/kennel actions that target "owner" apply to all pooches/kennels owned.
            # An optional filter narrows which ones are affected; no selector is needed.
            # Exception: clone_pooch with target_type "owner" needs a selector to pick which pooch to clone.
            _kennel_only_actions = {"modify_kennel_capacity", "upgrade_kennel", "delete_kennel"}
            _selector_picking_actions = {"clone_pooch"}
            _is_kennel_action = action_type in _kennel_only_actions
            _needs_selector = action_type in _selector_picking_actions
            common_allowed |= {"filter", "pooch_filter", "save_as"}
            if _needs_selector:
                common_allowed |= {"selector", "count", "use_saved"}
                if "use_saved" not in parameters:
                    if "selector" in parameters:
                        self._validate_entity_selector(params_path, parameters, "selector")
                    self._validate_optional_int(params_path, parameters, "count", minimum=1)
                else:
                    self._validate_optional_string(params_path, parameters, "use_saved", allow_blank=False)
                    if "selector" in parameters:
                        self.error(params_path, "'selector' and 'use_saved' cannot both be present")
            if "filter" in parameters:
                if _is_kennel_action:
                    self._validate_kennel_filter(f"{params_path}.filter", parameters["filter"], allow_counts=False)
                else:
                    self._validate_pooch_filter(
                        f"{params_path}.filter", parameters["filter"], allow_counts=False, allow_location=True
                    )
            if "pooch_filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.pooch_filter",
                    parameters["pooch_filter"],
                    allow_counts=False,
                    allow_location=True,
                )
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)

        elif target_type == "server":
            # Server-scoped actions target a pool of pooches (or owners) across the server.
            _server_pool_values = {"stray", "dead", "in_hell", "all_alive", "all", "saved", "owner", "saved_owner"}
            _server_selector_values = {"all", "random", "first"}
            common_allowed |= {
                "pool",
                "selector",
                "count",
                "filter",
                "save_as",
                "use_saved",
                "save_owner",
                "destination",
                "mutations",
                "amount",
                "min_amount",
                "max_amount",
                "exclude_amount",
                "roll_once",
                "mode",
                "age",
            }
            if "pool" in parameters:
                pool_val = parameters["pool"]
                if not isinstance(pool_val, str) or pool_val.strip().lower() not in _server_pool_values:
                    self.error(
                        params_path,
                        f"'pool' must be one of: {', '.join(sorted(_server_pool_values))}",
                    )
            if "selector" in parameters:
                sel_val = parameters["selector"]
                if not isinstance(sel_val, str) or sel_val.strip().lower() not in _server_selector_values:
                    self.error(
                        params_path,
                        f"'selector' must be one of: {', '.join(sorted(_server_selector_values))}",
                    )
            if "destination" in parameters:
                dest_val = parameters["destination"]
                if not isinstance(dest_val, str) or dest_val.strip().lower() not in {
                    "town",
                    "kennel",
                    "graveyard",
                    "hell",
                    "vendor",
                }:
                    self.error(
                        params_path,
                        "'destination' must be 'town', 'kennel', 'graveyard', 'hell', or 'vendor'",
                    )
            if "filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.filter", parameters["filter"], allow_counts=False, allow_location=True
                )

        # Cross-target-type checks for carry-forward params
        if "save_kennel" in parameters and "save_as" not in parameters:
            self.error(params_path, "'save_kennel' requires 'save_as'")
        if "save_kennel" in parameters and target_type != "pooch":
            self.error(params_path, "'save_kennel' is only valid on pooch target actions")

        if "save_owner" in parameters and "save_as" not in parameters:
            self.error(params_path, "'save_owner' requires 'save_as'")
        if "save_owner" in parameters and target_type not in {"pooch", "server"}:
            self.error(params_path, "'save_owner' is only valid on pooch or server target actions")

        if action_type in {"modify_money", "modify_bloodskulls"}:
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"amount", "min_amount", "max_amount", "exclude_amount", "roll_once", "mode"},
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_optional_bool(params_path, parameters, "roll_once")
            if "mode" in parameters and parameters["mode"] not in {"modify", "set"}:
                self.error(params_path, "'mode' must be 'modify' or 'set'")

            if target_type == "server":
                pool_val = str(parameters.get("pool", "")).strip().lower()
                if pool_val not in {"owner", "saved_owner"}:
                    self.error(
                        params_path,
                        f"'{action_type}' with target_type 'server' requires pool 'owner' or 'saved_owner'",
                    )
            else:
                self._validate_target_type(path, action_type, target_type, {"owner"})

        elif action_type in {"modify_base_health", "modify_pooch_age"}:
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"amount", "min_amount", "max_amount", "exclude_amount", "roll_once", "mode"},
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_optional_bool(params_path, parameters, "roll_once")
            if "mode" in parameters and parameters["mode"] not in {"modify", "set"}:
                self.error(params_path, "'mode' must be 'modify' or 'set'")
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "injure_pooch":
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed
                | {"injury", "min_severity", "max_severity", "min_health_impact", "max_health_impact", "roll_once"},
            )
            if "injury" in parameters:
                if self.injury_names and str(parameters["injury"]).strip().lower() not in self.injury_names:
                    self.error(
                        params_path,
                        f"'injury' must be one of: {', '.join(sorted(self.injury_names))}",
                    )
            if "min_severity" in parameters:
                self._validate_enum_string(params_path, parameters, "min_severity", EVENT_SEVERITY_VALUES)
            if "max_severity" in parameters:
                self._validate_enum_string(params_path, parameters, "max_severity", EVENT_SEVERITY_VALUES)
            if "min_health_impact" in parameters:
                self._validate_enum_string(params_path, parameters, "min_health_impact", HEALTH_IMPACT_VALUES)
            if "max_health_impact" in parameters:
                self._validate_enum_string(params_path, parameters, "max_health_impact", HEALTH_IMPACT_VALUES)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "kill_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type in {"add_mutation", "remove_mutation"}:
            _mutation_filter_keys = {
                "mutation",
                "min_rarity",
                "max_rarity",
                "min_health_impact",
                "max_health_impact",
            }
            if target_type == "server":
                # Server actions may pass a list via "mutations" or a single name via "mutation"
                self._validate_allowed_keys(params_path, parameters, common_allowed | {"mutation", "mutations"})
                if "mutation" in parameters:
                    self._validate_optional_known_name(params_path, parameters, "mutation", self.mutation_names)
                if "mutations" in parameters:
                    mutations_val = parameters["mutations"]
                    if not isinstance(mutations_val, list):
                        self.error(f"{params_path}.mutations", "must be a list")
                    else:
                        for idx, m in enumerate(mutations_val):
                            if not isinstance(m, str):
                                self.error(f"{params_path}.mutations[{idx}]", "must be a string")
                            elif self.mutation_names and m.strip().lower() not in self.mutation_names:
                                self.error(f"{params_path}.mutations[{idx}]", f"unknown mutation '{m}'")
            else:
                self._validate_allowed_keys(
                    params_path, parameters, common_allowed | _mutation_filter_keys | {"mutations"}
                )
                self._validate_optional_known_name(params_path, parameters, "mutation", self.mutation_names)
                if "mutations" in parameters:
                    mutations_val = parameters["mutations"]
                    if not isinstance(mutations_val, list):
                        self.error(f"{params_path}.mutations", "must be a list")
                    else:
                        for idx, m in enumerate(mutations_val):
                            if not isinstance(m, str):
                                self.error(f"{params_path}.mutations[{idx}]", "must be a string")
                            elif self.mutation_names and m.strip().lower() not in self.mutation_names:
                                self.error(f"{params_path}.mutations[{idx}]", f"unknown mutation '{m}'")
                if "min_rarity" in parameters:
                    self._validate_enum_string(params_path, parameters, "min_rarity", RARITY_VALUES)
                if "max_rarity" in parameters:
                    self._validate_enum_string(params_path, parameters, "max_rarity", RARITY_VALUES)
                if "min_health_impact" in parameters:
                    self._validate_enum_string(params_path, parameters, "min_health_impact", HEALTH_IMPACT_VALUES)
                if "max_health_impact" in parameters:
                    self._validate_enum_string(params_path, parameters, "max_health_impact", HEALTH_IMPACT_VALUES)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "add_breed":
            self._validate_allowed_keys(
                params_path, parameters, common_allowed | {"breed", "weight", "min_rarity", "max_rarity"}
            )
            self._validate_optional_known_name(params_path, parameters, "breed", self.breed_names)
            self._validate_optional_number(params_path, parameters, "weight", minimum_exclusive=0)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "remove_breed":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"breed", "min_rarity", "max_rarity"})
            self._validate_optional_known_name(params_path, parameters, "breed", self.breed_names)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "transfer_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"new_owner_discord_id", "vendor_id"})
            self._validate_requires_one_of(params_path, parameters, [("new_owner_discord_id",), ("vendor_id",)])
            self._validate_mutually_exclusive(params_path, parameters, "new_owner_discord_id", "vendor_id")
            self._validate_optional_int(params_path, parameters, "new_owner_discord_id", minimum=1)
            self._validate_optional_int(params_path, parameters, "vendor_id", minimum=1)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner"})

        elif action_type == "create_pooch":
            self._validate_allowed_keys(
                params_path,
                parameters,
                {
                    "name",
                    "sex",
                    "age",
                    "base_health",
                    "strength",
                    "cuteness",
                    "fluffiness",
                    "intelligence",
                    "dexterity",
                    "fertility",
                    "aggressiveness",
                    "constitution",
                    "breeding_cooldown",
                    "destination",
                    "save_as",
                    # server-only extras
                    "pool",
                    "selector",
                    "count",
                    "filter",
                    "save_slot",
                    "breeds",
                    "mutations",
                },
            )
            self._validate_optional_string(params_path, parameters, "name", allow_blank=False)
            self._validate_enum_string(params_path, parameters, "sex", SEX_VALUES)
            self._validate_optional_int(params_path, parameters, "age", minimum=0)
            self._validate_optional_int(params_path, parameters, "base_health")
            self._validate_optional_int(params_path, parameters, "breeding_cooldown", minimum=0)
            self._validate_enum_string(
                params_path, parameters, "destination", {"kennel", "graveyard", "hell", "town", "vendor"}
            )
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            self._validate_target_type(path, action_type, target_type, {"owner", "server"})

        elif action_type == "clone_pooch":
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed
                | {
                    "name",
                    "sex",
                    "age",
                    "base_health",
                    "strength",
                    "cuteness",
                    "fluffiness",
                    "intelligence",
                    "dexterity",
                    "fertility",
                    "aggressiveness",
                    "constitution",
                    "breeding_cooldown",
                    "destination",
                    "save_as",
                },
            )
            self._validate_optional_string(params_path, parameters, "name", allow_blank=False)
            self._validate_enum_string(params_path, parameters, "sex", SEX_VALUES)
            self._validate_optional_int(params_path, parameters, "age", minimum=0)
            self._validate_optional_int(params_path, parameters, "base_health")
            self._validate_optional_int(params_path, parameters, "breeding_cooldown", minimum=0)
            self._validate_enum_string(
                params_path, parameters, "destination", {"kennel", "graveyard", "hell", "town", "vendor"}
            )
            self._validate_save_as_with_targets(params_path, parameters, {"clone", "source"})
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "modify_kennel_capacity":
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"amount", "min_amount", "max_amount", "exclude_amount", "roll_once", "mode"},
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_optional_bool(params_path, parameters, "roll_once")
            if "mode" in parameters and parameters["mode"] not in {"modify", "set"}:
                self.error(params_path, "'mode' must be 'modify' or 'set'")
            self._validate_target_type(path, action_type, target_type, {"kennel", "owner"})

        elif action_type == "upgrade_kennel":
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"amount", "min_amount", "max_amount", "exclude_amount", "roll_once"},
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_optional_bool(params_path, parameters, "roll_once")
            self._validate_target_type(path, action_type, target_type, {"kennel", "owner"})

        elif action_type == "delete_kennel":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"kennel", "owner"})

        elif action_type == "rename_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"name"})
            self._validate_optional_string(params_path, parameters, "name", allow_blank=False)
            self._validate_requires_one_of(params_path, parameters, [("name",)])
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type in {"modify_breeding_cooldown"}:
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"reset", "amount", "min_amount", "max_amount", "exclude_amount", "roll_once", "mode"},
            )
            is_reset = self._validate_optional_bool(params_path, parameters, "reset")
            if is_reset:
                for disallowed in ("amount", "min_amount", "max_amount", "roll_once", "mode"):
                    if disallowed in parameters:
                        self.error(params_path, f"'{disallowed}' cannot be used with 'reset'")
            else:
                if "amount" in parameters or "min_amount" in parameters:
                    self._validate_amount_group(params_path, parameters)
                self._validate_requires_one_of(
                    params_path, parameters, [("reset",), ("amount",), ("min_amount", "max_amount")]
                )
                self._validate_optional_bool(params_path, parameters, "roll_once")
                if "mode" in parameters and parameters["mode"] not in {"modify", "set"}:
                    self.error(params_path, "'mode' must be 'modify' or 'set'")
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "start_event":
            self._validate_allowed_keys(params_path, parameters, {"event", "random_event"})
            event_name = self._validate_optional_known_name(params_path, parameters, "event", self.event_names)
            random_event = self._validate_optional_bool(params_path, parameters, "random_event")
            if random_event is not True and event_name is None:
                self.error(params_path, "requires 'event' unless 'random_event' is true")
            self._validate_target_type(path, action_type, target_type, {"owner"})

        elif action_type == "breed_pooches":
            self._validate_allowed_keys(
                params_path,
                parameters,
                {
                    "selector",
                    "filter",
                    "first_pooch_selector",
                    "first_filter",
                    "second_pooch_selector",
                    "second_filter",
                    "require_unique",
                    "require_same",
                    "baby_name",
                    "baby_sex",
                    "baby_age",
                    "baby_base_health",
                    "baby_breeding_cooldown",
                    "save_as",
                    "destination",
                    # server-only extras
                    "pool",
                    "count",
                    "save_slot",
                },
            )
            if "first_pooch_selector" in parameters:
                self._validate_entity_selector(params_path, parameters, "first_pooch_selector")
            if "second_pooch_selector" in parameters:
                self._validate_entity_selector(params_path, parameters, "second_pooch_selector")
            if "first_filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.first_filter", parameters["first_filter"], allow_counts=False, allow_location=True
                )
            if "second_filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.second_filter", parameters["second_filter"], allow_counts=False, allow_location=True
                )
            require_unique = self._validate_optional_bool(params_path, parameters, "require_unique")
            require_same = self._validate_optional_bool(params_path, parameters, "require_same")
            if require_unique is True and require_same is True:
                self.error(params_path, "'require_unique' and 'require_same' cannot both be true")
            self._validate_optional_string(params_path, parameters, "baby_name", allow_blank=False)
            self._validate_enum_string(params_path, parameters, "baby_sex", SEX_VALUES)
            self._validate_optional_int(params_path, parameters, "baby_age", minimum=0)
            self._validate_optional_int(params_path, parameters, "baby_base_health")
            self._validate_optional_int(params_path, parameters, "baby_breeding_cooldown", minimum=0)
            self._validate_save_as_with_targets(params_path, parameters, {"baby", "first_parent", "second_parent"})
            self._validate_target_type(path, action_type, target_type, {"owner", "kennel", "server"})

        elif action_type == "sell_pooch":
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"vendor_id", "vendor_selector", "value_multiplier"},
            )
            self._validate_optional_int(params_path, parameters, "vendor_id", minimum=1)
            if "vendor_selector" in parameters:
                self._validate_enum_string(params_path, parameters, "vendor_selector", {"random"})
            if "vendor_id" in parameters and "vendor_selector" in parameters:
                self.error(params_path, "'vendor_id' and 'vendor_selector' cannot both be present")
            self._validate_optional_number(params_path, parameters, "value_multiplier", minimum_exclusive=0)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner"})

        elif action_type == "buy_pooch":
            self._validate_allowed_keys(
                params_path,
                parameters,
                {
                    "vendor_id",
                    "vendor_selector",
                    "pooch_selector",
                    "pooch_filter",
                    "value_multiplier",
                    "destination",
                    "save_as",
                },
            )
            self._validate_optional_int(params_path, parameters, "vendor_id", minimum=1)
            if "vendor_selector" in parameters:
                self._validate_enum_string(params_path, parameters, "vendor_selector", {"random"})
            if "vendor_id" in parameters and "vendor_selector" in parameters:
                self.error(params_path, "'vendor_id' and 'vendor_selector' cannot both be present")
            if "pooch_selector" in parameters:
                self._validate_enum_string(params_path, parameters, "pooch_selector", {"random"})
            if "pooch_filter" in parameters:
                self._validate_pooch_filter(
                    f"{params_path}.pooch_filter",
                    parameters["pooch_filter"],
                    allow_counts=False,
                    allow_location=False,
                )
            self._validate_optional_number(params_path, parameters, "value_multiplier", minimum_exclusive=0)
            self._validate_enum_string(params_path, parameters, "destination", {"kennel", "graveyard", "hell", "town"})
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            self._validate_target_type(path, action_type, target_type, {"owner"})

        elif action_type == "release_stray":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "enter_kennel":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"server"})

        elif action_type == "enter_vendor_stock":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"server"})

        elif action_type == "select_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"save_as", "featured"})
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "start_stray_event":
            self._validate_allowed_keys(params_path, parameters, {"event"})
            if "event" not in parameters:
                self.error(params_path, "requires 'event'")
            self._validate_target_type(path, action_type, target_type, {"owner", "server"})

        elif action_type == "start_server_event":
            self._validate_allowed_keys(params_path, parameters, {"event"})
            if "event" not in parameters:
                self.error(params_path, "requires 'event'")
            self._validate_target_type(path, action_type, target_type, {"server"})

        elif action_type == "receive_stray":
            self._validate_allowed_keys(
                params_path,
                parameters,
                {"destination", "count", "use_saved", "save_as"},
            )
            self._validate_optional_int(params_path, parameters, "count", minimum=1)
            self._validate_enum_string(params_path, parameters, "destination", {"kennel", "graveyard", "hell", "town"})
            self._validate_optional_string(params_path, parameters, "use_saved", allow_blank=False)
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            if "use_saved" in parameters and "count" in parameters:
                self.error(params_path, "'use_saved' and 'count' cannot both be present")
            self._validate_target_type(path, action_type, target_type, {"owner", "pooch"})

        elif action_type == "revive_pooch":
            self._validate_allowed_keys(
                params_path, parameters, common_allowed | {"destination", "save_as", "save_slot"}
            )
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "damn_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "modify_base_health":
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"amount", "min_amount", "max_amount", "exclude_amount", "roll_once", "mode"},
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_optional_bool(params_path, parameters, "roll_once")
            if "mode" in parameters and parameters["mode"] not in {"modify", "set"}:
                self.error(params_path, "'mode' must be 'modify' or 'set'")
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type in {
            "modify_strength",
            "modify_cuteness",
            "modify_fluffiness",
            "modify_intelligence",
            "modify_dexterity",
            "modify_fertility",
            "modify_aggressiveness",
            "modify_constitution",
        }:
            self._validate_allowed_keys(
                params_path,
                parameters,
                common_allowed | {"amount", "min_amount", "max_amount", "exclude_amount", "roll_once", "mode"},
            )
            self._validate_requires_one_of(params_path, parameters, [("amount",), ("min_amount", "max_amount")])
            self._validate_amount_group(params_path, parameters)
            self._validate_optional_bool(params_path, parameters, "roll_once")
            if "mode" in parameters and parameters["mode"] not in {"add", "set"}:
                self.error(params_path, "'mode' must be 'add' or 'set'")
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "set_pooch_age":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"age"})
            self._validate_optional_int(params_path, parameters, "age", minimum=0)
            self._validate_requires_one_of(params_path, parameters, [("age",)])
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner", "server"})

        elif action_type == "conjure_pooch":
            self._validate_allowed_keys(params_path, parameters, {"num_rolls", "destination", "save_as"})
            self._validate_optional_int(params_path, parameters, "num_rolls", minimum=1)
            if "destination" in parameters:
                self._validate_enum_string(
                    params_path, parameters, "destination", {"kennel", "graveyard", "hell", "town"}
                )
            self._validate_optional_string(params_path, parameters, "save_as", allow_blank=False)
            self._validate_target_type(path, action_type, target_type, {"owner"})

        elif action_type == "sacrifice_pooch":
            self._validate_allowed_keys(params_path, parameters, common_allowed | {"value_multiplier"})
            self._validate_optional_number(params_path, parameters, "value_multiplier", minimum_exclusive=0)
            self._validate_target_type(path, action_type, target_type, {"pooch", "kennel", "owner"})

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
        self._validate_int_list(path, filter_data, "exclude_capacity")
        self._validate_min_max_pair(path, filter_data, "min_upgrade_tier", "max_upgrade_tier", minimum=0)
        self._validate_int_list(path, filter_data, "exclude_upgrade_tier")
        max_pooches = filter_data.get("max_pooches")
        if max_pooches is not None:
            if isinstance(max_pooches, bool) or not isinstance(max_pooches, int):
                self.error(
                    f"{path}.max_pooches",
                    "must be an integer (use negative values like -1 for capacity-relative limits)",
                )
            else:
                self._validate_optional_int(path, filter_data, "min_pooches", minimum=0)
        elif "min_pooches" in filter_data:
            self._validate_optional_int(path, filter_data, "min_pooches", minimum=0)
        self._validate_int_list(path, filter_data, "exclude_pooches")
        self._validate_optional_bool(path, filter_data, "at_capacity")

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
        self._validate_int_list(path, filter_data, "exclude_age")
        self._validate_enum_string(path, filter_data, "sex", SEX_VALUES)
        self._validate_min_max_pair(path, filter_data, "min_health", "max_health")
        self._validate_int_list(path, filter_data, "exclude_health")
        self._validate_optional_bool(path, filter_data, "is_virgin")
        self._validate_optional_bool(path, filter_data, "is_alive")
        self._validate_min_max_pair(
            path,
            filter_data,
            "min_breeding_cooldown",
            "max_breeding_cooldown",
            minimum=0,
        )
        self._validate_int_list(path, filter_data, "exclude_breeding_cooldown")

        self._validate_name_list(path, filter_data, "has_any_breed", self.breed_names)
        self._validate_name_list(path, filter_data, "has_all_breeds", self.breed_names)
        self._validate_name_list(path, filter_data, "exclude_breeds", self.breed_names)
        self._validate_name_list(path, filter_data, "has_any_mutation", self.mutation_names)
        self._validate_name_list(path, filter_data, "has_all_mutations", self.mutation_names)
        self._validate_name_list(path, filter_data, "exclude_mutations", self.mutation_names)

        if allow_location:
            self._validate_enum_string(path, filter_data, "location", LOCATION_VALUES)

    def _validate_owner_filter(self, path: str, filter_data: Any, *, allow_count: bool = False) -> None:
        if filter_data is None:
            return
        if not isinstance(filter_data, dict):
            self.error(path, "must be an object")
            return

        if not filter_data:
            return

        allowed_keys = _OWNER_SUBFILTER_ALLOWED_KEYS if allow_count else _OWNER_FILTER_ALLOWED_KEYS
        self._validate_unknown_keys(path, filter_data, allowed_keys)

        if allow_count:
            self._validate_min_max_pair(path, filter_data, "min_count", "max_count", minimum=1)

        self._validate_seasons_list(path, filter_data)
        self._validate_min_max_pair(path, filter_data, "min_money", "max_money")
        self._validate_int_list(path, filter_data, "exclude_money")
        self._validate_min_max_pair(path, filter_data, "min_bloodskulls", "max_bloodskulls")
        self._validate_int_list(path, filter_data, "exclude_bloodskulls")
        self._validate_min_max_pair(path, filter_data, "min_pooches", "max_pooches", minimum=0)
        self._validate_int_list(path, filter_data, "exclude_pooches")
        self._validate_min_max_pair(path, filter_data, "min_kennels", "max_kennels", minimum=0)
        self._validate_int_list(path, filter_data, "exclude_kennels")

        kennels = filter_data.get("kennels", [])
        if not isinstance(kennels, list):
            self.error(f"{path}.kennels", "must be a list")
        else:
            for idx, kennel_filter in enumerate(kennels):
                self._validate_kennel_filter(f"{path}.kennels[{idx}]", kennel_filter, allow_counts=True)

        for pool_field in ("pooches", "graveyard_pooches", "hell_pooches"):
            pool_data = filter_data.get(pool_field, [])
            if not isinstance(pool_data, list):
                self.error(f"{path}.{pool_field}", "must be a list")
            else:
                for idx, pooch_filter in enumerate(pool_data):
                    self._validate_pooch_filter(
                        f"{path}.{pool_field}[{idx}]",
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

        if "exclude_amount" in value:
            if not (min_present and max_present):
                self.error(path, "'exclude_amount' is only valid when 'min_amount' and 'max_amount' are both set")
            exclude = value["exclude_amount"]
            if not isinstance(exclude, list) or not all(isinstance(v, int) for v in exclude):
                self.error(path, "'exclude_amount' must be a list of integers")

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
            self.error(f"{path}.{field_name}", "must be 'selected', 'random', or 'all'")
            return None
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in _SELECTOR_TOKENS:
                return normalized
        self.error(f"{path}.{field_name}", "must be 'selected', 'random', or 'all'")
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

    _VALID_SEASONS = {"spring", "summer", "autumn", "winter"}

    def _validate_seasons_list(self, path: str, value: dict[str, Any]) -> None:
        """Validate an optional ``seasons`` key — must be a non-empty list of valid season strings."""
        if "seasons" not in value:
            return
        raw = value["seasons"]
        if not isinstance(raw, list) or not raw:
            self.error(f"{path}.seasons", "must be a non-empty list of season strings")
            return
        for s in raw:
            if not isinstance(s, str) or s.strip().lower() not in self._VALID_SEASONS:
                self.error(
                    f"{path}.seasons",
                    f"'{s}' is not a valid season (must be one of: {', '.join(sorted(self._VALID_SEASONS))})",
                )

    def _validate_int_list(self, path: str, value: dict[str, Any], field_name: str) -> list[int] | None:
        if field_name not in value:
            return None
        raw_value = value[field_name]
        if not isinstance(raw_value, list):
            self.error(f"{path}.{field_name}", "must be a list of integers")
            return None
        validated: list[int] = []
        for idx, item in enumerate(raw_value):
            if isinstance(item, bool) or not isinstance(item, int):
                self.error(f"{path}.{field_name}[{idx}]", "must be an integer")
                continue
            validated.append(item)
        return validated

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

    def _validate_stat_weights(self, path: str, stat_weights: Any) -> None:
        """Validate a stat_weights list on an outcome."""
        sw_path = f"{path}.stat_weights"
        if not isinstance(stat_weights, list):
            self.error(sw_path, "must be a list")
            return
        _allowed = {"stat", "pooch", "scale", "pivot", "direction"}
        for i, entry in enumerate(stat_weights):
            ep = f"{sw_path}[{i}]"
            if not isinstance(entry, dict):
                self.error(ep, "each entry must be an object")
                continue
            self._validate_unknown_keys(ep, entry, _allowed)
            if "stat" not in entry or not isinstance(entry["stat"], str) or not entry["stat"].strip():
                self.error(ep, "'stat' is required and must be a non-empty string")
            if "scale" not in entry or isinstance(entry["scale"], bool) or not isinstance(entry["scale"], (int, float)):
                self.error(ep, "'scale' is required and must be a number")
            if "pivot" in entry:
                if isinstance(entry["pivot"], bool) or not isinstance(entry["pivot"], (int, float)):
                    self.error(ep, "'pivot' must be a number")
            if "direction" in entry:
                if isinstance(entry["direction"], bool) or not isinstance(entry["direction"], (int, float)):
                    self.error(ep, "'direction' must be a number")

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

    def _validate_save_as_with_targets(self, path: str, parameters: dict[str, Any], valid_targets: set[str]) -> None:
        """
        Validate a save_as field that can be either:
          - a plain string (slot name, target defaults to the action-type default)
          - a list of {"slot": str, "target": str} dicts

        valid_targets: set of accepted target strings for this action type.
        """
        if "save_as" not in parameters:
            return
        raw = parameters["save_as"]
        if isinstance(raw, str):
            if not raw.strip():
                self.error(f"{path}.save_as", "must not be blank")
            return
        if not isinstance(raw, list):
            self.error(f"{path}.save_as", "must be a string or a list of {slot, target} objects")
            return
        for i, item in enumerate(raw):
            item_path = f"{path}.save_as[{i}]"
            if not isinstance(item, dict):
                self.error(item_path, "must be an object with 'slot' and 'target'")
                continue
            slot = item.get("slot")
            if not isinstance(slot, str) or not slot.strip():
                self.error(f"{item_path}.slot", "must be a non-blank string")
            target = item.get("target")
            if target is not None:
                if not isinstance(target, str) or target.strip().lower() not in valid_targets:
                    self.error(
                        f"{item_path}.target",
                        f"must be one of: {', '.join(sorted(valid_targets))}",
                    )
