from typing import Any

from sqlalchemy import delete, select

from logger import get_logger

from ...models import (
    Breed,
    Event,
    EventAction,
    Mutation,
    ServerEvent,
    ServerEventOption,
    ServerEventOutcome,
)
from ...session import session_scope
from .utils import (
    EVENT_SEVERITY_VALUES,
    RARITY_VALUES,
    RESOURCE_ROOT,
    BaseEventValidator,
    load_categorized_resource_objects,
    resolve_event_action_parameters,
)

logger = get_logger("database/load/load_resources/server_events")

SERVER_EVENTS_ROOT = RESOURCE_ROOT / "server_events"

_SERVER_EVENT_ALLOWED_KEYS = {
    "name",
    "description",
    "flavor_text",
    "severity",
    "rarity",
    "min_owners",
    "max_participants",
    "resolution_strategy",
    "advanced_options",
    "actions",
    "options",
    "outcomes",
}

_SERVER_EVENT_OPTION_ALLOWED_KEYS = {
    "label",
    "description",
    "min_money",
    "min_bloodskulls",
    "requires_pooch_selection",
    "advanced_options",
    "actions",
}

_SERVER_EVENT_OUTCOME_ALLOWED_KEYS = {
    "label",
    "description",
    "message",
    "min_rank",
    "max_rank",
    "chance",
    "advanced_options",
    "actions",
}


class _ServerEventValidator(BaseEventValidator):
    def validate_server_events_json(self, server_events_json: dict[str, Any]) -> None:
        if not isinstance(server_events_json, dict):
            self.error("server_events", "root value must be an object keyed by category")
            return

        for category_name, events in server_events_json.items():
            category_path = f"server_events.{category_name}"
            if not isinstance(events, dict):
                self.error(category_path, "category value must be an object keyed by event name")
                continue
            for event_name, attributes in events.items():
                self._validate_server_event(category_name, event_name, attributes)

    def _validate_server_event(self, category_name: str, event_name: str, attributes: Any) -> None:
        path = f"server_events.{category_name}.{event_name}"
        if not isinstance(attributes, dict):
            self.error(path, "server event definition must be an object")
            return

        self._validate_unknown_keys(path, attributes, _SERVER_EVENT_ALLOWED_KEYS)

        self._validate_optional_string(path, attributes, "name", allow_blank=False)
        self._validate_optional_string(path, attributes, "description")
        self._validate_optional_string(path, attributes, "flavor_text")
        self._validate_optional_json_object(path, attributes, "advanced_options")
        self._validate_enum_string(path, attributes, "severity", EVENT_SEVERITY_VALUES)
        self._validate_enum_string(path, attributes, "rarity", RARITY_VALUES)
        self._validate_optional_int(path, attributes, "min_owners", minimum=1)
        self._validate_optional_int(path, attributes, "max_participants", minimum=0)
        strategy = self._validate_optional_string(path, attributes, "resolution_strategy", allow_blank=False)
        if strategy is not None and strategy.strip().lower() not in {
            "random_winner",
            "selected_pooch_health",
            "participation_only",
        }:
            self.error(
                f"{path}.resolution_strategy",
                "must be one of: participation_only, random_winner, selected_pooch_health",
            )

        actions = self._validate_actions_list(path, attributes.get("actions", []), "actions")
        options = self._validate_server_options_list(path, attributes.get("options", []))
        outcomes = self._validate_server_outcomes_list(path, attributes.get("outcomes", []))

        if not options:
            self.error(path, "server events must define at least one option")
        if not actions and not options and not outcomes:
            self.error(path, "server events must define actions, options, or outcomes")

    def _validate_server_options_list(self, path: str, options: Any) -> list[dict[str, Any]]:
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

            self._validate_unknown_keys(current_path, option, _SERVER_EVENT_OPTION_ALLOWED_KEYS)
            self._validate_optional_string(current_path, option, "label", allow_blank=False)
            self._validate_optional_string(current_path, option, "description")
            self._validate_optional_int(current_path, option, "min_money", minimum=0)
            self._validate_optional_int(current_path, option, "min_bloodskulls", minimum=0)
            self._validate_optional_bool(current_path, option, "requires_pooch_selection")
            self._validate_optional_json_object(current_path, option, "advanced_options")
            self._validate_actions_list(current_path, option.get("actions", []), "actions")
            validated.append(option)
        return validated

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
            self._validate_optional_int(current_path, outcome, "min_rank", minimum=1)
            self._validate_optional_int(current_path, outcome, "max_rank", minimum=1)
            min_rank = outcome.get("min_rank")
            max_rank = outcome.get("max_rank")
            if isinstance(min_rank, int) and isinstance(max_rank, int) and min_rank > max_rank:
                self.error(current_path, "min_rank cannot be greater than max_rank")
            chance = self._validate_optional_probability(current_path, outcome, "chance")
            if chance is not None:
                explicit_chances.append(chance)
            self._validate_optional_json_object(current_path, outcome, "advanced_options")
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

    server_events_json = load_categorized_resource_objects(SERVER_EVENTS_ROOT, "server_event")

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

        validator = _ServerEventValidator(
            breed_names=breed_names,
            mutation_names=mutation_names,
            event_names=event_names,
        )
        validator.validate_server_events_json(server_events_json)
        validator.raise_if_invalid()

        await session.execute(delete(EventAction).where(EventAction.server_event_outcome_id.is_not(None)))
        await session.execute(delete(EventAction).where(EventAction.server_event_option_id.is_not(None)))
        await session.execute(delete(EventAction).where(EventAction.server_event_id.is_not(None)))
        await session.execute(delete(ServerEventOutcome))
        await session.execute(delete(ServerEventOption))
        await session.execute(delete(ServerEvent))

        for event_category, events in server_events_json.items():
            for event_name, attributes in events.items():
                event = ServerEvent(
                    name=str(event_name),
                    category=str(event_category),
                    description=str(attributes.get("description", f"{event_name} is a server event.")),
                    flavor_text=str(attributes.get("flavor_text", "")),
                    severity=str(attributes.get("severity", "minor")).lower(),
                    rarity=str(attributes.get("rarity", "common")).lower(),
                    min_owners=int(attributes.get("min_owners", 1)),
                    max_participants=int(attributes.get("max_participants", 0)),
                    resolution_strategy=str(attributes.get("resolution_strategy", "random_winner")).lower(),
                    advanced_options=attributes.get("advanced_options", {}),
                )
                session.add(event)
                await session.flush()

                for idx, action_data in enumerate(attributes.get("actions", [])):
                    action = EventAction(
                        server_event_id=event.id,
                        action_order=idx,
                        action_type=str(action_data.get("action_type")).lower(),
                        target_type=str(action_data.get("target_type", "owner")).lower(),
                        parameters=resolve_event_action_parameters(
                            action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                        ),
                    )
                    session.add(action)

                for opt_idx, option_data in enumerate(attributes.get("options", [])):
                    option = ServerEventOption(
                        server_event_id=event.id,
                        option_order=opt_idx,
                        label=str(option_data.get("label", f"Option {opt_idx + 1}")),
                        description=str(option_data.get("description", "")),
                        min_money=int(option_data.get("min_money", 0)),
                        min_bloodskulls=int(option_data.get("min_bloodskulls", 0)),
                        requires_pooch_selection=bool(option_data.get("requires_pooch_selection", False)),
                        advanced_options=option_data.get("advanced_options", {}),
                    )
                    session.add(option)
                    await session.flush()

                    for act_idx, opt_action_data in enumerate(option_data.get("actions", [])):
                        option_action = EventAction(
                            server_event_option_id=option.id,
                            action_order=act_idx,
                            action_type=str(opt_action_data.get("action_type")).lower(),
                            target_type=str(opt_action_data.get("target_type", "owner")).lower(),
                            parameters=resolve_event_action_parameters(
                                opt_action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                            ),
                        )
                        session.add(option_action)

                for outcome_idx, outcome_data in enumerate(attributes.get("outcomes", [])):
                    outcome = ServerEventOutcome(
                        server_event_id=event.id,
                        outcome_order=outcome_idx,
                        label=str(outcome_data.get("label", "")),
                        description=str(outcome_data.get("description", "")),
                        message=str(outcome_data.get("message", "")),
                        min_rank=int(outcome_data["min_rank"]) if "min_rank" in outcome_data else None,
                        max_rank=int(outcome_data["max_rank"]) if "max_rank" in outcome_data else None,
                        chance=float(outcome_data["chance"]) if "chance" in outcome_data else None,
                        advanced_options=outcome_data.get("advanced_options", {}),
                    )
                    session.add(outcome)
                    await session.flush()

                    for outcome_action_idx, outcome_action_data in enumerate(outcome_data.get("actions", [])):
                        outcome_action = EventAction(
                            server_event_outcome_id=outcome.id,
                            action_order=outcome_action_idx,
                            action_type=str(outcome_action_data.get("action_type")).lower(),
                            target_type=str(outcome_action_data.get("target_type", "owner")).lower(),
                            parameters=resolve_event_action_parameters(
                                outcome_action_data.get("parameters", {}),
                                breed_name_to_id,
                                mutation_name_to_id,
                            ),
                        )
                        session.add(outcome_action)

    logger.info("Finished loading server events.")
