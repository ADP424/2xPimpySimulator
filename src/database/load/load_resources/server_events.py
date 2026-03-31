from collections import defaultdict
from pathlib import Path
from typing import Any

import json5
from sqlalchemy import delete, select

from src.logger import get_logger

from ...models import (
    Breed,
    Event,
    EventAction,
    Injury,
    Mutation,
    ServerEvent,
    ServerEventMenu,
    ServerEventMenuOption,
    ServerEventOutcome,
)
from ...session import session_scope
from .utils import (
    EVENT_SEVERITY_VALUES,
    RARITY_VALUES,
    RESOURCE_ROOT,
    BaseEventValidator,
    _iter_files,
    resolve_event_action_parameters,
)

logger = get_logger("database/load/load_resources/server_events")

SERVER_EVENTS_ROOT = RESOURCE_ROOT / "server_events"
_VALID_TIERS = {"minor", "major"}
_JSONC_SUFFIXES = {".jsonc", ".json"}


def _load_server_event_objects(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Load server events from a 3-level structure: <tier>/<category>/<file>.jsonc.

    Returns a dict keyed by tier, then event name, with each value being the attributes dict
    plus injected ``_tier`` and ``_category`` keys for later use.
    """

    def _titleize_slug(value: str) -> str:
        normalized = value.replace("-", "_").strip("_")
        parts = [part for part in normalized.split("_") if part]
        return " ".join(part.capitalize() for part in parts) or value

    # Keyed by tier -> category -> name -> attributes
    resources: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
    seen_names: dict[str, Path] = {}

    for path in _iter_files(root, _JSONC_SUFFIXES):
        relative = path.relative_to(root)
        if len(relative.parts) < 3:
            raise ValueError(
                f"server_event file must live inside a tier/category folder "
                f"(e.g. minor/community/event.jsonc): {path}"
            )

        tier_raw = relative.parts[0].strip().lower()
        if tier_raw not in _VALID_TIERS:
            raise ValueError(f"server_event tier folder must be 'minor' or 'major', got '{tier_raw}': {path}")
        tier = tier_raw
        category = _titleize_slug(relative.parts[1])

        payload = json5.loads(path.read_text(encoding="utf8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected an object in {path}")

        name = str(payload.get("name") or _titleize_slug(path.stem)).strip()
        if not name:
            raise ValueError(f"server_event file has a blank name: {path}")
        if name in seen_names:
            raise ValueError(f"Duplicate server_event name '{name}' in {seen_names[name]} and {path}")
        seen_names[name] = path

        attrs = dict(payload)
        attrs.pop("name", None)
        attrs["_tier"] = tier
        attrs["_category"] = category
        resources[tier][name] = attrs

    # Flatten to a single tier -> {name: attrs} dict (validator iterates over tiers as top-level)
    return {tier: dict(by_name) for tier, by_name in resources.items()}


_SERVER_EVENT_ALLOWED_KEYS = {
    "name",
    "description",
    "flavor_text",
    "severity",
    "rarity",
    "filter",
    "default_actions",
    "parameters",
    "actions",
    "menus",
    "outcomes",
}

_SERVER_EVENT_FILTER_ALLOWED_KEYS = {
    "seasons",
    "min_owners",
    "max_owners",
    "min_strays",
    "max_strays",
    "min_dead",
    "max_dead",
    "min_in_hell",
    "max_in_hell",
    "stray_pooches",
    "dead_pooches",
    "hell_pooches",
    "owners",
}

_SERVER_MENU_ALLOWED_KEYS = {
    "label",
    "description",
    "max_uses_per_player",
    "depends_on",
    "options",
    "parameters",
}

_SERVER_MENU_OPTION_ALLOWED_KEYS = {
    "label",
    "description",
    "filter",
    "requires",
    "actions",
    "scoring",
    "parameters",
}

_SERVER_MENU_OPTION_REQUIRES_ALLOWED_KEYS = {"pooch"}
_SERVER_MENU_OPTION_REQUIRES_POOCH_ALLOWED_KEYS = {"filter"}

_SCORING_ALLOWED_KEYS = {"aggregate", "sources"}
_SCORING_SOURCE_ALLOWED_KEYS = {"type", "stat", "scale", "pivot", "direction", "min", "max", "value"}
_SCORING_AGGREGATE_VALUES = {"sum", "average", "max"}
_SCORING_SOURCE_TYPES = {"random", "pooch_stat", "owner_stat", "constant"}

_SERVER_EVENT_OUTCOME_ALLOWED_KEYS = {
    "label",
    "description",
    "message",
    "target",
    "min_rank",
    "max_rank",
    "chance",
    "parameters",
    "actions",
}

_OUTCOME_TARGET_VALUES = {"ranked_players", "all_participants", "server", "non_participants"}


class _ServerEventValidator(BaseEventValidator):
    def validate_server_events_json(self, server_events_json: dict[str, Any]) -> None:
        """Validate the flat {tier: {name: attrs}} structure from _load_server_event_objects."""
        if not isinstance(server_events_json, dict):
            self.error("server_events", "root value must be an object keyed by tier")
            return

        for tier_name, events in server_events_json.items():
            tier_path = f"server_events.{tier_name}"
            if not isinstance(events, dict):
                self.error(tier_path, "tier value must be an object keyed by event name")
                continue
            for event_name, attributes in events.items():
                self._validate_server_event(tier_name, event_name, attributes)

    def _validate_server_event(self, tier_name: str, event_name: str, attributes: Any) -> None:
        path = f"server_events.{tier_name}.{event_name}"
        if not isinstance(attributes, dict):
            self.error(path, "server event definition must be an object")
            return

        # Strip internal loader keys before validating public-facing keys
        public_attrs = {k: v for k, v in attributes.items() if not k.startswith("_")}
        self._validate_unknown_keys(path, public_attrs, _SERVER_EVENT_ALLOWED_KEYS)

        self._validate_optional_string(path, attributes, "name", allow_blank=False)
        self._validate_optional_string(path, public_attrs, "description")
        self._validate_optional_string(path, public_attrs, "flavor_text")
        self._validate_optional_json_object(path, public_attrs, "parameters")
        self._validate_enum_string(path, public_attrs, "severity", EVENT_SEVERITY_VALUES)
        self._validate_enum_string(path, public_attrs, "rarity", RARITY_VALUES)

        if "filter" in public_attrs:
            self._validate_server_event_filter(f"{path}.filter", public_attrs["filter"])

        self._validate_actions_list(path, public_attrs.get("actions", []), "actions")
        self._validate_actions_list(path, public_attrs.get("default_actions", []), "default_actions")

        menus = self._validate_server_menus(path, public_attrs.get("menus", {}))
        outcomes = self._validate_server_outcomes_list(path, public_attrs.get("outcomes", []))

        has_actions = bool(public_attrs.get("actions"))
        has_default_actions = bool(public_attrs.get("default_actions"))
        if not menus and not outcomes and not has_actions and not has_default_actions:
            self.error(path, "server events must define actions, menus, or outcomes")

    def _validate_server_event_filter(self, path: str, filter_data: Any) -> None:
        if not isinstance(filter_data, dict):
            self.error(path, "must be an object")
            return

        self._validate_unknown_keys(path, filter_data, _SERVER_EVENT_FILTER_ALLOWED_KEYS)

        self._validate_seasons_list(path, filter_data)
        self._validate_optional_int(path, filter_data, "min_owners", minimum=1)
        self._validate_optional_int(path, filter_data, "max_owners", minimum=1)
        self._validate_optional_int(path, filter_data, "min_strays", minimum=0)
        self._validate_optional_int(path, filter_data, "max_strays", minimum=0)
        self._validate_optional_int(path, filter_data, "min_dead", minimum=0)
        self._validate_optional_int(path, filter_data, "max_dead", minimum=0)
        self._validate_optional_int(path, filter_data, "min_in_hell", minimum=0)
        self._validate_optional_int(path, filter_data, "max_in_hell", minimum=0)

        for pool_field in ("stray_pooches", "dead_pooches", "hell_pooches"):
            pool_data = filter_data.get(pool_field, [])
            if not isinstance(pool_data, list):
                self.error(f"{path}.{pool_field}", "must be a list")
            else:
                for idx, pooch_filter in enumerate(pool_data):
                    self._validate_pooch_filter(
                        f"{path}.{pool_field}[{idx}]",
                        pooch_filter,
                        allow_counts=True,
                        allow_location=False,
                    )

        owners = filter_data.get("owners", [])
        if not isinstance(owners, list):
            self.error(f"{path}.owners", "must be a list")
        else:
            for idx, owner_filter in enumerate(owners):
                self._validate_owner_filter(f"{path}.owners[{idx}]", owner_filter, allow_count=True)

    def _validate_server_menus(self, path: str, menus: Any) -> dict[str, Any]:
        menus_path = f"{path}.menus"
        if menus is None or menus == {}:
            return {}
        if not isinstance(menus, dict):
            self.error(menus_path, "must be an object keyed by menu name")
            return {}

        validated: dict[str, Any] = {}
        menu_names: set[str] = set(menus.keys())

        for menu_name, menu_data in menus.items():
            menu_path = f"{menus_path}.{menu_name}"
            if not isinstance(menu_data, dict):
                self.error(menu_path, "menu definition must be an object")
                continue

            self._validate_unknown_keys(menu_path, menu_data, _SERVER_MENU_ALLOWED_KEYS)
            self._validate_optional_string(menu_path, menu_data, "label")
            self._validate_optional_string(menu_path, menu_data, "description")
            self._validate_optional_json_object(menu_path, menu_data, "parameters")

            max_uses = menu_data.get("max_uses_per_player", 1)
            if max_uses != "unlimited":
                if isinstance(max_uses, bool) or not isinstance(max_uses, int) or max_uses < 1:
                    self.error(f"{menu_path}.max_uses_per_player", "must be a positive integer or 'unlimited'")

            depends_on = menu_data.get("depends_on", [])
            if not isinstance(depends_on, list):
                self.error(f"{menu_path}.depends_on", "must be a list of menu names")
            else:
                for dep in depends_on:
                    if not isinstance(dep, str):
                        self.error(f"{menu_path}.depends_on", "each dependency must be a string menu name")
                    elif dep not in menu_names:
                        self.error(f"{menu_path}.depends_on", f"references unknown menu '{dep}'")
                    elif dep == menu_name:
                        self.error(f"{menu_path}.depends_on", "a menu cannot depend on itself")

            options = menu_data.get("options", [])
            if not isinstance(options, list) or not options:
                self.error(menu_path, "menu must define at least one option")
            else:
                for opt_idx, option_data in enumerate(options):
                    self._validate_server_menu_option(f"{menu_path}.options[{opt_idx}]", option_data)

            validated[menu_name] = menu_data

        return validated

    def _validate_server_menu_option(self, path: str, option_data: Any) -> None:
        if not isinstance(option_data, dict):
            self.error(path, "option must be an object")
            return

        self._validate_unknown_keys(path, option_data, _SERVER_MENU_OPTION_ALLOWED_KEYS)
        self._validate_optional_string(path, option_data, "label", allow_blank=False)
        self._validate_optional_string(path, option_data, "description")
        self._validate_optional_json_object(path, option_data, "parameters")

        if "filter" in option_data:
            self._validate_owner_filter(f"{path}.filter", option_data["filter"])

        if "requires" in option_data:
            req = option_data["requires"]
            if not isinstance(req, dict):
                self.error(f"{path}.requires", "must be an object")
            else:
                self._validate_unknown_keys(f"{path}.requires", req, _SERVER_MENU_OPTION_REQUIRES_ALLOWED_KEYS)
                if "pooch" in req:
                    pooch_req = req["pooch"]
                    if not isinstance(pooch_req, dict):
                        self.error(f"{path}.requires.pooch", "must be an object")
                    else:
                        self._validate_unknown_keys(
                            f"{path}.requires.pooch", pooch_req, _SERVER_MENU_OPTION_REQUIRES_POOCH_ALLOWED_KEYS
                        )
                        if "filter" in pooch_req:
                            self._validate_pooch_filter(
                                f"{path}.requires.pooch.filter",
                                pooch_req["filter"],
                                allow_counts=False,
                                allow_location=True,
                            )

        self._validate_actions_list(path, option_data.get("actions", []), "actions")

        if "scoring" in option_data:
            self._validate_scoring(f"{path}.scoring", option_data["scoring"])

    def _validate_scoring(self, path: str, scoring: Any) -> None:
        if not isinstance(scoring, dict):
            self.error(path, "must be an object")
            return

        self._validate_unknown_keys(path, scoring, _SCORING_ALLOWED_KEYS)

        if "aggregate" in scoring:
            agg = scoring["aggregate"]
            if not isinstance(agg, str) or agg.strip().lower() not in _SCORING_AGGREGATE_VALUES:
                self.error(f"{path}.aggregate", f"must be one of: {', '.join(sorted(_SCORING_AGGREGATE_VALUES))}")

        sources = scoring.get("sources", [])
        if not isinstance(sources, list):
            self.error(f"{path}.sources", "must be a list")
            return

        for idx, source in enumerate(sources):
            self._validate_scoring_source(f"{path}.sources[{idx}]", source)

    def _validate_scoring_source(self, path: str, source: Any) -> None:
        if not isinstance(source, dict):
            self.error(path, "must be an object")
            return

        self._validate_unknown_keys(path, source, _SCORING_SOURCE_ALLOWED_KEYS)

        source_type = source.get("type")
        if not isinstance(source_type, str) or source_type.strip().lower() not in _SCORING_SOURCE_TYPES:
            self.error(f"{path}.type", f"must be one of: {', '.join(sorted(_SCORING_SOURCE_TYPES))}")
            return

        source_type = source_type.strip().lower()

        if source_type == "random":
            self._validate_optional_number(path, source, "min")
            self._validate_optional_number(path, source, "max")

        elif source_type in {"pooch_stat", "owner_stat"}:
            if "stat" not in source or not isinstance(source.get("stat"), str):
                self.error(f"{path}.stat", "required string for pooch_stat / owner_stat source")
            self._validate_optional_number(path, source, "scale")
            self._validate_optional_number(path, source, "pivot")
            self._validate_optional_number(path, source, "direction")

        elif source_type == "constant":
            self._validate_optional_number(path, source, "value")

    def _validate_server_outcomes_list(self, path: str, outcomes: Any) -> list[dict[str, Any]]:
        outcomes_path = f"{path}.outcomes"
        if not isinstance(outcomes, list):
            self.error(outcomes_path, "must be a list")
            return []

        validated: list[dict[str, Any]] = []
        explicit_chances: list[float] = []

        for index, outcome in enumerate(outcomes):
            current_path = f"{outcomes_path}[{index}]"
            if not isinstance(outcome, dict):
                self.error(current_path, "outcome must be an object")
                continue

            self._validate_unknown_keys(current_path, outcome, _SERVER_EVENT_OUTCOME_ALLOWED_KEYS)
            self._validate_optional_string(current_path, outcome, "label")
            self._validate_optional_string(current_path, outcome, "description")
            self._validate_optional_string(current_path, outcome, "message")

            target = outcome.get("target", "ranked_players")
            if isinstance(target, str) and target.strip().lower() not in _OUTCOME_TARGET_VALUES:
                self.error(
                    f"{current_path}.target",
                    f"must be one of: {', '.join(sorted(_OUTCOME_TARGET_VALUES))}",
                )

            self._validate_optional_int(current_path, outcome, "min_rank", minimum=1)
            self._validate_optional_int(current_path, outcome, "max_rank", minimum=1)
            min_rank = outcome.get("min_rank")
            max_rank = outcome.get("max_rank")
            if isinstance(min_rank, int) and isinstance(max_rank, int) and min_rank > max_rank:
                self.error(current_path, "min_rank cannot be greater than max_rank")
            chance = self._validate_optional_probability(current_path, outcome, "chance")
            if chance is not None:
                explicit_chances.append(chance)
            self._validate_optional_json_object(current_path, outcome, "parameters")
            self._validate_actions_list(current_path, outcome.get("actions", []), "actions")
            validated.append(outcome)

        if explicit_chances:
            total = sum(explicit_chances)
            all_explicit = len(explicit_chances) == len(validated)
            if all_explicit:
                if abs(total - 1.0) > 0.001:
                    self.error(
                        outcomes_path,
                        f"all outcomes have explicit chances but they sum to {total:.4f} (must sum to 1.0)",
                    )
            else:
                if total > 1.0 + 0.001:
                    self.error(
                        outcomes_path,
                        f"explicit outcome chances sum to {total:.4f} which exceeds 1.0",
                    )

        return validated


async def load_server_events():
    logger.info("Loading server events from 'resources/server_events/**/*.jsonc' into the database...")

    server_events_json = _load_server_event_objects(SERVER_EVENTS_ROOT)

    async with session_scope() as session:
        breed_names = {name.strip().lower() for name in (await session.execute(select(Breed.name))).scalars().all()}
        mutation_names = {
            name.strip().lower() for name in (await session.execute(select(Mutation.name))).scalars().all()
        }
        event_names = {name.strip().lower() for name in (await session.execute(select(Event.name))).scalars().all()}
        breed_name_to_id = {
            breed.name.strip().lower(): breed.id for breed in (await session.execute(select(Breed))).scalars().all()
        }
        mutation_name_to_id = {
            mutation.name.strip().lower(): mutation.id
            for mutation in (await session.execute(select(Mutation))).scalars().all()
        }
        injury_names = {name.strip().lower() for name in (await session.execute(select(Injury.name))).scalars().all()}

        validator = _ServerEventValidator(
            breed_names=breed_names,
            mutation_names=mutation_names,
            event_names=event_names,
            injury_names=injury_names,
        )
        validator.validate_server_events_json(server_events_json)
        validator.raise_if_invalid()

        # Delete in dependency order: actions → menu options → menus → outcomes → events
        await session.execute(delete(EventAction).where(EventAction.server_event_outcome_id.is_not(None)))
        await session.execute(delete(EventAction).where(EventAction.server_event_menu_option_id.is_not(None)))
        await session.execute(delete(EventAction).where(EventAction.server_event_id.is_not(None)))
        await session.execute(delete(ServerEventOutcome))
        await session.execute(delete(ServerEventMenuOption))
        await session.execute(delete(ServerEventMenu))
        await session.execute(delete(ServerEvent))

        for tier_name, events in server_events_json.items():
            for event_name, attributes in events.items():
                raw_filter = attributes.get("filter", {})
                default_actions_raw = attributes.get("default_actions", [])

                event = ServerEvent(
                    name=str(event_name),
                    tier=str(tier_name).lower(),
                    category=str(attributes.get("_category", tier_name)),
                    description=str(attributes.get("description", f"{event_name} is a server event.")),
                    flavor_text=str(attributes.get("flavor_text", "")),
                    severity=str(attributes.get("severity", "minor")).lower(),
                    rarity=str(attributes.get("rarity", "common")).lower(),
                    filter=raw_filter if isinstance(raw_filter, dict) else {},
                    default_actions_data=default_actions_raw if isinstance(default_actions_raw, list) else [],
                    parameters=attributes.get("parameters", {}),
                )
                session.add(event)
                await session.flush()

                # Top-level trigger actions (server-scoped)
                for idx, action_data in enumerate(attributes.get("actions", [])):
                    action = EventAction(
                        server_event_id=event.id,
                        action_order=idx,
                        action_type=str(action_data.get("action_type")).lower(),
                        target_type=str(action_data.get("target_type", "server")).lower(),
                        repeat=int(action_data.get("repeat", 1)),
                        parameters=resolve_event_action_parameters(
                            action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                        ),
                    )
                    session.add(action)

                # Named menus
                menus_data: dict[str, Any] = attributes.get("menus", {})
                for menu_order, (menu_name, menu_data) in enumerate(menus_data.items()):
                    max_uses_raw = menu_data.get("max_uses_per_player", 1)
                    max_uses = -1 if max_uses_raw == "unlimited" else int(max_uses_raw)

                    menu = ServerEventMenu(
                        server_event_id=event.id,
                        menu_order=menu_order,
                        name=str(menu_name),
                        label=str(menu_data.get("label", menu_name)),
                        description=str(menu_data.get("description", "")),
                        max_uses_per_player=max_uses,
                        depends_on=list(menu_data.get("depends_on", [])),
                        parameters=menu_data.get("parameters", {}),
                    )
                    session.add(menu)
                    await session.flush()

                    for opt_idx, option_data in enumerate(menu_data.get("options", [])):
                        menu_option = ServerEventMenuOption(
                            menu_id=menu.id,
                            option_order=opt_idx,
                            label=str(option_data.get("label", f"Option {opt_idx + 1}")),
                            description=str(option_data.get("description", "")),
                            filter=option_data.get("filter", {}),
                            requires=option_data.get("requires", {}),
                            scoring=option_data.get("scoring", {}),
                            parameters=option_data.get("parameters", {}),
                        )
                        session.add(menu_option)
                        await session.flush()

                        for act_idx, opt_action_data in enumerate(option_data.get("actions", [])):
                            option_action = EventAction(
                                server_event_menu_option_id=menu_option.id,
                                action_order=act_idx,
                                action_type=str(opt_action_data.get("action_type")).lower(),
                                target_type=str(opt_action_data.get("target_type", "owner")).lower(),
                                repeat=int(opt_action_data.get("repeat", 1)),
                                parameters=resolve_event_action_parameters(
                                    opt_action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                                ),
                            )
                            session.add(option_action)

                # Outcomes
                for outcome_idx, outcome_data in enumerate(attributes.get("outcomes", [])):
                    outcome = ServerEventOutcome(
                        server_event_id=event.id,
                        outcome_order=outcome_idx,
                        label=str(outcome_data.get("label", "")),
                        description=str(outcome_data.get("description", "")),
                        message=str(outcome_data.get("message", "")),
                        target=str(outcome_data.get("target", "ranked_players")).lower(),
                        min_rank=outcome_data["min_rank"] if "min_rank" in outcome_data else None,
                        max_rank=outcome_data["max_rank"] if "max_rank" in outcome_data else None,
                        chance=float(outcome_data["chance"]) if "chance" in outcome_data else None,
                        parameters=outcome_data.get("parameters", {}),
                    )
                    session.add(outcome)
                    await session.flush()

                    for outcome_action_idx, outcome_action_data in enumerate(outcome_data.get("actions", [])):
                        outcome_action = EventAction(
                            server_event_outcome_id=outcome.id,
                            action_order=outcome_action_idx,
                            action_type=str(outcome_action_data.get("action_type")).lower(),
                            target_type=str(outcome_action_data.get("target_type", "owner")).lower(),
                            repeat=int(outcome_action_data.get("repeat", 1)),
                            parameters=resolve_event_action_parameters(
                                outcome_action_data.get("parameters", {}),
                                breed_name_to_id,
                                mutation_name_to_id,
                            ),
                        )
                        session.add(outcome_action)

    logger.info("Finished loading server events.")
