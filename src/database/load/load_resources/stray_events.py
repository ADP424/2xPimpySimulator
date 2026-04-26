from typing import Any

from sqlalchemy import delete, select

from src.database.session import session_scope
from src.logger import get_logger

from ...models import (
    Breed,
    Injury,
    Mutation,
    StrayEvent,
    StrayEventAction,
    StrayEventOutcome,
)
from .utils import (
    EVENT_SEVERITY_VALUES,
    RARITY_VALUES,
    RESOURCE_ROOT,
    BaseEventValidator,
    load_categorized_resource_objects,
    resolve_event_action_parameters,
)

logger = get_logger("database/load/load_resources/stray_events")

STRAY_EVENTS_ROOT = RESOURCE_ROOT / "stray_events"

_EVENT_ALLOWED_KEYS = {
    "name",
    "severity",
    "rarity",
    "triggered_only",
    "filter",
    "actions",
    "outcomes",
}

_OUTCOME_ALLOWED_KEYS = {
    "chance",
    "stat_weights",
    "actions",
}

_STRAY_ACTION_TYPES = {
    "modify_base_health",
    "injure_pooch",
    "modify_pooch_age",
    "kill_pooch",
    "add_mutation",
    "remove_mutation",
    "add_breed",
    "create_pooch",
    "clone_pooch",
    "rename_pooch",
    "modify_breeding_cooldown",
    "breed_pooches",
    "enter_kennel",
    "enter_vendor_stock",
    "start_stray_event",
    "select_pooch",
    "modify_strength",
    "modify_cuteness",
    "modify_fluffiness",
    "modify_intelligence",
    "modify_dexterity",
    "modify_fertility",
    "modify_aggressiveness",
    "modify_constitution",
}

_STRAY_SELECTORS = {"random", "random_exclude", "all", "all_exclude"}


def _resolve_stray_event_filter(attributes: dict[str, Any]) -> dict[str, Any]:
    return dict(attributes.get("filter", {}))


class _StrayEventValidator(BaseEventValidator):
    def validate_stray_events_json(self, stray_events_json: dict[str, Any]) -> None:
        if not isinstance(stray_events_json, dict):
            self.error("stray_events", "root value must be an object keyed by category")
            return

        for category_name, events in stray_events_json.items():
            category_path = f"stray_events.{category_name}"
            if not isinstance(events, dict):
                self.error(category_path, "category value must be an object keyed by event name")
                continue
            for event_name, attributes in events.items():
                self._validate_event(category_name, event_name, attributes)

    def _validate_event(self, category_name: str, event_name: str, attributes: Any) -> None:
        path = f"stray_events.{category_name}.{event_name}"
        if not isinstance(attributes, dict):
            self.error(path, "event definition must be an object")
            return

        self._validate_unknown_keys(path, attributes, _EVENT_ALLOWED_KEYS)
        self._validate_optional_string(path, attributes, "name", allow_blank=False)
        self._validate_enum_string(path, attributes, "severity", EVENT_SEVERITY_VALUES)
        self._validate_enum_string(path, attributes, "rarity", RARITY_VALUES)
        self._validate_optional_bool(path, attributes, "triggered_only")
        self._validate_stray_event_filter(f"{path}.filter", attributes.get("filter"))
        actions = self._validate_stray_actions_list(path, attributes.get("actions", []))
        outcomes = self._validate_outcomes_list(path, attributes.get("outcomes", []))

        if not actions and not outcomes:
            self.error(path, "stray events must define at least one action or outcome")

    def _validate_stray_event_filter(self, path: str, filter_spec: Any) -> None:
        if filter_spec is None:
            return
        if not isinstance(filter_spec, dict):
            self.error(path, "filter must be an object")
            return

        allowed = {"seasons", "min_count", "max_count", "description", "pooches"}
        self._validate_unknown_keys(path, filter_spec, allowed)
        self._validate_seasons_list(path, filter_spec)
        self._validate_optional_int(path, filter_spec, "min_count", minimum=0)
        self._validate_optional_int(path, filter_spec, "max_count", minimum=0)

        if "pooches" in filter_spec:
            pooches = filter_spec["pooches"]
            if not isinstance(pooches, list):
                self.error(f"{path}.pooches", "must be a list of pooch filter specs")
            else:
                for i, pf in enumerate(pooches):
                    if isinstance(pf, dict):
                        self._validate_pooch_filter(f"{path}.pooches[{i}]", pf, allow_counts=True, allow_location=False)

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
            chance = self._validate_optional_probability(current_path, outcome, "chance")
            stat_weights = outcome.get("stat_weights", [])
            self._validate_stat_weights(current_path, stat_weights)
            # Only count as a fixed (reserved) chance if there are no stat_weights
            if chance is not None and not stat_weights:
                fixed_chances.append(chance)
            self._validate_stray_actions_list(current_path, outcome.get("actions", []))
            validated.append(outcome)

        if fixed_chances:
            total = sum(fixed_chances)
            if total > 1.0 + 0.001:
                self.error(
                    outcomes_path,
                    f"fixed outcome chances sum to {total:.4f} which exceeds 1.0",
                )

        return validated

    def _validate_stray_actions_list(self, path: str, actions: Any) -> list[dict[str, Any]]:
        actions_path = f"{path}.actions"
        if not isinstance(actions, list):
            self.error(actions_path, "must be a list")
            return []

        validated: list[dict[str, Any]] = []
        for index, action in enumerate(actions):
            current_path = f"{actions_path}[{index}]"
            if not isinstance(action, dict):
                self.error(current_path, "action must be an object")
                continue

            allowed_keys = {"action_type", "parameters", "repeat", "filter"}
            self._validate_unknown_keys(current_path, action, allowed_keys)

            action_type_raw = action.get("action_type")
            if not isinstance(action_type_raw, str) or action_type_raw.strip().lower() not in _STRAY_ACTION_TYPES:
                self.error(
                    current_path,
                    f"'action_type' must be one of: {sorted(_STRAY_ACTION_TYPES)}; got {action_type_raw!r}",
                )
                continue

            repeat = self._validate_optional_int(current_path, action, "repeat", minimum=1)
            if repeat is not None and repeat < 1:
                self.error(f"{current_path}.repeat", "must be at least 1")

            parameters = action.get("parameters", {})
            if not isinstance(parameters, dict):
                self.error(f"{current_path}.parameters", "must be an object")
                continue

            # Validate selector in parameters — only stray selectors allowed
            if "selector" in parameters:
                sel = parameters["selector"]
                if not isinstance(sel, str) or sel.strip().lower() not in _STRAY_SELECTORS:
                    self.error(
                        f"{current_path}.parameters.selector",
                        f"must be one of {sorted(_STRAY_SELECTORS)}; got {sel!r}",
                    )

            # Action-level filter
            if "filter" in parameters:
                self._validate_pooch_filter(
                    f"{current_path}.parameters.filter", parameters["filter"], allow_counts=False, allow_location=False
                )

            validated.append(action)

        return validated


async def load_stray_events():
    """
    Load stray events.

    Returns
    -------
    Any
        The result of calling `load_stray_events`.
    """

    logger.info("Loading stray events from stray event resources into the database...")

    stray_events_json = load_categorized_resource_objects(STRAY_EVENTS_ROOT, "stray event")
    if not stray_events_json:
        logger.info("No stray events found — skipping.")
        return

    event_names = {event_name.strip().lower() for events in stray_events_json.values() for event_name in events}

    async with session_scope() as session:
        breed_names = {name.strip().lower() for name in (await session.execute(select(Breed.name))).scalars().all()}
        mutation_names = {
            name.strip().lower() for name in (await session.execute(select(Mutation.name))).scalars().all()
        }
        injury_names = {name.strip().lower() for name in (await session.execute(select(Injury.name))).scalars().all()}
        breed_name_to_id = {
            breed.name.strip().lower(): breed.id for breed in (await session.execute(select(Breed))).scalars().all()
        }
        mutation_name_to_id = {
            mutation.name.strip().lower(): mutation.id
            for mutation in (await session.execute(select(Mutation))).scalars().all()
        }

        validator = _StrayEventValidator(
            breed_names=breed_names,
            mutation_names=mutation_names,
            event_names=event_names,
            injury_names=injury_names,
        )
        validator.validate_stray_events_json(stray_events_json)
        validator.raise_if_invalid()

        await session.execute(delete(StrayEventAction))
        await session.execute(delete(StrayEventOutcome))
        await session.execute(delete(StrayEvent))

        for event_category, events in stray_events_json.items():
            for event_name, attributes in events.items():
                event = StrayEvent(
                    name=str(event_name),
                    category=str(event_category),
                    severity=str(attributes.get("severity", "minor")).lower(),
                    rarity=str(attributes.get("rarity", "common")).lower(),
                    triggered_only=bool(attributes.get("triggered_only", False)),
                    filter=_resolve_stray_event_filter(attributes),
                )
                session.add(event)
                await session.flush()

                for idx, action_data in enumerate(attributes.get("actions", [])):
                    action = StrayEventAction(
                        stray_event_id=event.id,
                        action_order=idx,
                        action_type=str(action_data.get("action_type")).lower(),
                        repeat=int(action_data.get("repeat", 1)),
                        parameters=resolve_event_action_parameters(
                            action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                        ),
                    )
                    session.add(action)

                for outcome_idx, outcome_data in enumerate(attributes.get("outcomes", [])):
                    outcome = StrayEventOutcome(
                        stray_event_id=event.id,
                        outcome_order=outcome_idx,
                        chance=float(outcome_data["chance"]) if "chance" in outcome_data else None,
                        stat_weights=list(outcome_data.get("stat_weights", [])),
                    )
                    session.add(outcome)
                    await session.flush()

                    for act_idx, action_data in enumerate(outcome_data.get("actions", [])):
                        action = StrayEventAction(
                            stray_event_outcome_id=outcome.id,
                            action_order=act_idx,
                            action_type=str(action_data.get("action_type")).lower(),
                            repeat=int(action_data.get("repeat", 1)),
                            parameters=resolve_event_action_parameters(
                                action_data.get("parameters", {}), breed_name_to_id, mutation_name_to_id
                            ),
                        )
                        session.add(action)

    logger.info("Finished loading stray events.")
