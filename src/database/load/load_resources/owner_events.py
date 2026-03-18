from typing import Any

from sqlalchemy import delete, select

from src.logger import get_logger

from ...models import Breed, Event, EventAction, EventOption, EventOutcome, Mutation
from ...session import session_scope
from .utils import (
    EVENT_SEVERITY_VALUES,
    RARITY_VALUES,
    RESOURCE_ROOT,
    BaseEventValidator,
    load_categorized_resource_objects,
    resolve_event_action_parameters,
)

logger = get_logger("database/load/load_resources/owner_events")

OWNER_EVENTS_ROOT = RESOURCE_ROOT / "owner_events"

_EVENT_ALLOWED_KEYS = {
    "name",
    "description",
    "flavor_text",
    "severity",
    "rarity",
    "requires_response",
    "response_timeout",
    "triggered_only",
    "filter",
    "advanced_options",
    "actions",
    "options",
}

_OPTION_ALLOWED_KEYS = {
    "label",
    "description",
    "default",
    "visible",
    "filter",
    "advanced_options",
    "actions",
    "outcomes",
}

_OUTCOME_ALLOWED_KEYS = {
    "label",
    "description",
    "message",
    "chance",
    "stat_weights",
    "advanced_options",
    "actions",
}


def _resolve_owner_event_filter(attributes: dict[str, Any]) -> dict[str, Any]:
    return dict(attributes.get("filter", {}))


def _resolve_owner_event_option_filter(attributes: dict[str, Any]) -> dict[str, Any]:
    return dict(attributes.get("filter", {}))


class _OwnerEventValidator(BaseEventValidator):
    def validate_owner_events_json(self, owner_events_json: dict[str, Any]) -> None:
        if not isinstance(owner_events_json, dict):
            self.error("owner_events", "root value must be an object keyed by category")
            return

        for category_name, events in owner_events_json.items():
            category_path = f"owner_events.{category_name}"
            if not isinstance(events, dict):
                self.error(category_path, "category value must be an object keyed by event name")
                continue
            for event_name, attributes in events.items():
                self._validate_event(category_name, event_name, attributes)

    def _validate_event(self, category_name: str, event_name: str, attributes: Any) -> None:
        path = f"owner_events.{category_name}.{event_name}"
        if not isinstance(attributes, dict):
            self.error(path, "event definition must be an object")
            return

        self._validate_unknown_keys(path, attributes, _EVENT_ALLOWED_KEYS)

        self._validate_optional_string(path, attributes, "name", allow_blank=False)
        self._validate_optional_string(path, attributes, "description")
        self._validate_optional_string(path, attributes, "flavor_text")
        self._validate_optional_json_object(path, attributes, "advanced_options")
        self._validate_enum_string(path, attributes, "severity", EVENT_SEVERITY_VALUES)
        self._validate_enum_string(path, attributes, "rarity", RARITY_VALUES)
        requires_response = self._validate_optional_bool(path, attributes, "requires_response")
        self._validate_optional_int(path, attributes, "response_timeout", minimum=1)
        self._validate_optional_bool(path, attributes, "triggered_only")
        self._validate_owner_filter(f"{path}.filter", attributes.get("filter"))
        actions = self._validate_actions_list(path, attributes.get("actions", []), "actions")
        options = self._validate_options_list(path, attributes.get("options", []), requires_response=requires_response)

        if requires_response is True and not options:
            self.error(path, "requires_response=true events must define at least one option")
        if not actions and not options:
            self.error(path, "events must define at least one action or option")

    def _validate_options_list(
        self, path: str, options: Any, *, requires_response: bool | None
    ) -> list[dict[str, Any]]:
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
            self._validate_optional_json_object(current_path, option, "advanced_options")
            is_default = self._validate_optional_bool(current_path, option, "default")
            is_visible = self._validate_optional_bool(current_path, option, "visible")

            if is_visible is False and not is_default:
                self.error(current_path, "'visible': false is only allowed on a default option")

            self._validate_owner_filter(f"{current_path}.filter", option.get("filter"))
            self._validate_actions_list(current_path, option.get("actions", []), "actions")
            self._validate_outcomes_list(current_path, option.get("outcomes", []))
            validated.append(option)

        if requires_response is True:
            defaults = [o for o in validated if o.get("default") is True]
            if len(defaults) == 0:
                self.error(
                    option_path,
                    "requires_response=true events must have exactly one option with 'default': true (none found)",
                )
            elif len(defaults) > 1:
                self.error(
                    option_path,
                    (
                        "requires_response=true events must have exactly one option with "
                        f"'default': true ({len(defaults)} found)"
                    ),
                )

        return validated

    def _validate_outcomes_list(self, path: str, outcomes: Any) -> list[dict[str, Any]]:
        outcomes_path = f"{path}.outcomes"
        if not isinstance(outcomes, list):
            self.error(outcomes_path, "must be a list")
            return []

        validated: list[dict[str, Any]] = []
        fixed_chances: list[float] = []

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
            chance = self._validate_optional_probability(current_path, outcome, "chance")
            stat_weights = outcome.get("stat_weights", [])
            self._validate_stat_weights(current_path, stat_weights)
            # Only count as a fixed (reserved) chance if there are no stat_weights
            if chance is not None and not stat_weights:
                fixed_chances.append(chance)
            self._validate_actions_list(current_path, outcome.get("actions", []), "actions")
            validated.append(outcome)

        if fixed_chances:
            total = sum(fixed_chances)
            if total > 1.0 + 0.001:
                self.error(
                    outcomes_path,
                    f"fixed outcome chances sum to {total:.4f} which exceeds 1.0",
                )

        return validated


async def load_owner_events():
    logger.info("Loading owner events from owner event resources into the database...")

    owner_events_json = load_categorized_resource_objects(OWNER_EVENTS_ROOT, "event")
    event_names = {event_name.strip().lower() for events in owner_events_json.values() for event_name in events}

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

        validator = _OwnerEventValidator(
            breed_names=breed_names,
            mutation_names=mutation_names,
            event_names=event_names,
        )
        validator.validate_owner_events_json(owner_events_json)
        validator.raise_if_invalid()

        await session.execute(delete(EventAction).where(EventAction.outcome_id.is_not(None)))
        await session.execute(delete(EventAction).where(EventAction.option_id.is_not(None)))
        await session.execute(delete(EventAction).where(EventAction.event_id.is_not(None)))
        await session.execute(delete(EventOutcome))
        await session.execute(delete(EventOption))
        await session.execute(delete(Event))

        for event_category, events in owner_events_json.items():
            for event_name, attributes in events.items():
                event = Event(
                    name=str(event_name),
                    category=str(event_category),
                    description=str(attributes.get("description", f"{event_name} is a random event that can occur.")),
                    flavor_text=str(attributes.get("flavor_text", "")),
                    severity=str(attributes.get("severity", "minor")).lower(),
                    rarity=str(attributes.get("rarity", "common")).lower(),
                    requires_response=bool(attributes.get("requires_response", False)),
                    response_timeout=attributes.get("response_timeout", 3600),
                    triggered_only=bool(attributes.get("triggered_only", False)),
                    filter=_resolve_owner_event_filter(attributes),
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
                        repeat=int(action_data.get("repeat", 1)),
                        parameters=resolve_event_action_parameters(
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
                        is_default=bool(option_data.get("default", False)),
                        is_visible=bool(option_data.get("visible", True)),
                        filter=_resolve_owner_event_option_filter(option_data),
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
                            repeat=int(opt_action_data.get("repeat", 1)),
                            parameters=resolve_event_action_parameters(
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
                            stat_weights=list(outcome_data.get("stat_weights", [])),
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
                                repeat=int(outcome_action_data.get("repeat", 1)),
                                parameters=resolve_event_action_parameters(
                                    outcome_action_data.get("parameters", {}),
                                    breed_name_to_id,
                                    mutation_name_to_id,
                                ),
                            )
                            session.add(outcome_action)

    logger.info("Finished loading owner events.")
