import logging
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    archive_active_event,
    create_active_owner_event,
    create_pooch,
    get_active_owner_event_by_id,
    get_owner_by_discord_id,
)
from database import get_owner_event_by_id as db_get_owner_event_by_id
from database import get_owner_event_by_name as db_get_owner_event_by_name
from database import (
    get_owner_event_option_by_id,
    get_pending_active_owner_event,
    get_random_eligible_owner_event_for_owner,
    give_bloodskulls_to_owner,
    give_money_to_owner,
    list_active_owner_events_for_owner,
)
from database import list_all_owner_events as db_list_all_owner_events
from database import (
    list_expired_active_owner_events,
    list_owner_event_history_for_owner,
    list_owners,
    modify_kennel_pooch_limit,
    modify_pooch_age,
    modify_pooch_base_health,
    remove_mutation_from_pooch,
    remove_random_mutation_from_pooch,
    rename_pooch,
    respond_to_active_owner_event,
    set_pooch_breeding_cooldown,
    set_pooch_dead,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
    update_active_event_result,
)
from database.utils import (
    check_owner_event_filter,
    get_matching_kennel_ids_for_owner,
    get_matching_pooch_ids_for_owner,
    get_random_matching_kennel_id_for_owner,
    get_random_matching_pooch_id_for_owner,
)

from .constants import (
    EVENT_HOURLY_TRIGGER_CHANCE,
    EVENT_MAX_ACTIVE_PER_OWNER,
)
from .models import (
    Event,
    EventContext,
    EventHistory,
    EventResult,
    TriggeredEvent,
    to_event,
    to_event_history,
    to_triggered_event,
)

if TYPE_CHECKING:
    from database.models import EventAction, EventOption, EventOutcome


logger = logging.getLogger(__name__)


async def get_active_events_for_owner(owner_discord_id: int, pending_only: bool = True) -> list[TriggeredEvent]:
    """
    Get all active events for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    pending_only: bool
        If True, only return events awaiting response.

    Returns
    -------
    list[TriggeredEvent]
        List of triggered events for the owner.
    """

    active_events = await list_active_owner_events_for_owner(owner_discord_id, pending_only=pending_only)
    return [await to_triggered_event(active_event) for active_event in active_events]


async def get_event_history(owner_discord_id: int, limit: int = 50) -> list[EventHistory]:
    """
    Get the event history for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    limit: int
        Maximum number of records to return.

    Returns
    -------
    list[EventHistory]
        List of typed event history records.
    """

    history = await list_owner_event_history_for_owner(owner_discord_id, limit)
    return [await to_event_history(record) for record in history]


async def get_pending_event(
    owner_discord_id: int, active_owner_event_id: Optional[int] = None
) -> Optional[TriggeredEvent]:
    """
    Get a specific pending event for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    active_owner_event_id: int, optional
        The specific active event ID to retrieve.

    Returns
    -------
    TriggeredEvent, optional
        The triggered event, or None if not found.
    """

    if active_owner_event_id is not None:
        active_event = await get_active_owner_event_by_id(active_owner_event_id)
        if active_event is None or active_event.owner_discord_id != owner_discord_id:
            return None
        if active_event.responded_at is not None:
            return None
    else:
        active_event = await get_pending_active_owner_event(owner_discord_id)
        if active_event is None:
            return None

    return await to_triggered_event(active_event)


async def list_all_owner_events() -> list[Event]:
    """
    List all available owner_events.

    Returns
    -------
    list[Event]
        A list of typed event information objects.
    """

    events = await db_list_all_owner_events()
    return [await to_event(event) for event in events]


async def process_expired_events(rng: Optional[random.Random] = None) -> list[tuple[int, int, EventResult]]:
    """
    Process all expired events that weren't responded to.

    Parameters
    ----------
    rng: Random, optional
        Random number generator for reproducibility.

    Returns
    -------
    list[tuple[int, int, EventResult]]
        List of (owner_discord_id, event_id, result) for processed owner_events.
    """

    if rng is None:
        rng = random.Random()

    expired_events = await list_expired_active_owner_events()
    results = []

    for active_event in expired_events:
        context = EventContext.from_dict(active_event.context)
        event = active_event.event

        # Start with any result already recorded from event-level actions at trigger time
        result = EventResult.from_dict(active_event.result_summary) if active_event.result_summary else EventResult()

        default_option = next((opt for opt in event.options if opt.is_default), None)
        responded_option_id = None

        if default_option is not None:
            responded_option_id = default_option.id
            option_result = await _execute_event_actions(
                active_event.owner_discord_id, default_option.actions, context, rng
            )
            result.merge(option_result)

            selected_outcome = _choose_option_outcome(default_option, rng)
            if selected_outcome is not None:
                outcome_result = await _execute_event_actions(
                    active_event.owner_discord_id, selected_outcome.actions, context, rng
                )
                result.merge(outcome_result)
                outcome_message = (
                    selected_outcome.message or selected_outcome.description or selected_outcome.label or None
                )
                result.extra_data["selected_outcome"] = {
                    "id": selected_outcome.id,
                    "label": selected_outcome.label,
                    "description": selected_outcome.description,
                    "message": selected_outcome.message,
                    "chance": selected_outcome.chance,
                }
                result.message = outcome_message or f"Event '{event.name}' expired. {default_option.label} was applied."
            else:
                result.message = f"Event '{event.name}' expired. {default_option.label} was applied."
        else:
            result.message = f"Event '{event.name}' expired without response. {result.message}".strip()

        await respond_to_active_owner_event(active_event.id, responded_option_id, result.to_dict())
        await archive_active_event(active_event.id, timed_out=True)

        results.append((active_event.owner_discord_id, event.id, result))
        logger.info(f"Processed expired event {active_event.id} for owner {active_event.owner_discord_id}")

    return results


def _choose_option_outcome(option: EventOption, rng: random.Random) -> Optional[EventOutcome]:
    explicit = [outcome for outcome in option.outcomes if outcome.chance is not None]
    if not explicit:
        return rng.choice(option.outcomes)

    total_explicit = sum(float(outcome.chance) for outcome in explicit)
    implicit = [outcome for outcome in option.outcomes if outcome.chance is None]

    weighted: list[tuple[EventOutcome, float]] = []
    if implicit and total_explicit < 1:
        remaining = 1 - total_explicit
        implicit_weight = remaining / len(implicit)
        weighted.extend((outcome, implicit_weight) for outcome in implicit)
    elif implicit:
        weighted.extend((outcome, 1.0) for outcome in implicit)

    weighted.extend((outcome, float(outcome.chance)) for outcome in explicit)
    total_weight = sum(weight for _, weight in weighted)
    if total_weight <= 0:
        return rng.choice(option.outcomes)

    roll = rng.uniform(0, total_weight)
    running_total = 0.0
    for outcome, weight in weighted:
        running_total += weight
        if roll <= running_total:
            return outcome

    return weighted[-1][0]


async def respond_to_event(
    owner_discord_id: int, active_owner_event_id: int, option_id: int, rng: Optional[random.Random] = None
) -> tuple[bool, str, Optional[EventResult]]:
    """
    Process a player's response to an event.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner responding.

    active_owner_event_id: int
        The ID of the active event being responded to.

    option_id: int
        The ID of the option selected.

    rng: Random, optional
        Random number generator for reproducibility.

    Returns
    -------
    tuple[bool, str, EventResult | None]
        Success status, message, and the result of the response.
    """

    if rng is None:
        rng = random.Random()

    active_event = await get_active_owner_event_by_id(active_owner_event_id)
    if active_event is None:
        return False, "Event not found.", None

    if active_event.owner_discord_id != owner_discord_id:
        return False, "This event is not for you.", None

    if active_event.responded_at is not None:
        return False, "You have already responded to this event.", None

    if active_event.expires_at and datetime.now(timezone.utc) > active_event.expires_at:
        await archive_active_event(active_owner_event_id, timed_out=True)
        return False, "This event has expired.", None

    option = await get_owner_event_option_by_id(option_id)
    if option is None:
        return False, "Invalid option.", None

    if option.event_id != active_event.event_id:
        return False, "This option is not valid for this event.", None

    if not option.is_visible:
        return False, "That option is not available.", None

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", None

    if owner.dollars < option.min_money:
        return False, f"You need at least ${option.min_money} to select this option.", None

    if owner.bloodskulls < option.min_bloodskulls:
        return False, f"You need at least {option.min_bloodskulls} bloodskulls to select this option.", None

    if not await _owner_passes_filter(owner_discord_id, option.filter):
        return False, "You do not currently meet the requirements for that option.", None

    context = EventContext.from_dict(active_event.context)
    # Merge with any result already recorded from event-level actions at trigger time
    result = EventResult.from_dict(active_event.result_summary) if active_event.result_summary else EventResult()
    option_result = await _execute_event_actions(owner_discord_id, option.actions, context, rng)
    result.merge(option_result)

    selected_outcome = _choose_option_outcome(option, rng)
    outcome_message = None
    if selected_outcome is not None:
        outcome_result = await _execute_event_actions(owner_discord_id, selected_outcome.actions, context, rng)
        result.merge(outcome_result)
        outcome_message = selected_outcome.message or selected_outcome.description or selected_outcome.label or None
        result.extra_data["selected_outcome"] = {
            "id": selected_outcome.id,
            "label": selected_outcome.label,
            "description": selected_outcome.description,
            "message": selected_outcome.message,
            "chance": selected_outcome.chance,
        }

    await respond_to_active_owner_event(active_owner_event_id, option_id, result.to_dict())
    await archive_active_event(active_owner_event_id)

    logger.info(f"Owner {owner_discord_id} responded to event {active_owner_event_id} with option {option_id}.")

    response_message = outcome_message or f"You selected: {option.label}."
    return True, response_message, result


async def run_hourly_event_check(rng_seed: Optional[int] = None) -> dict[int, list[TriggeredEvent]]:
    """
    Run the hourly event check for all owners.

    This should be called once per hour to potentially trigger events
    for each player.

    Parameters
    ----------
    rng_seed: int, optional
        Seed for the random number generator.

    Returns
    -------
    dict[int, list[TriggeredEvent]]
        Dictionary mapping owner Discord IDs to triggered owner_events.
    """

    if rng_seed is not None:
        rng = random.Random(rng_seed)
    else:
        rng = random.Random()

    await process_expired_events(rng)

    owners = await list_owners()

    triggered_events: dict[int, list[TriggeredEvent]] = {}

    for owner in owners:
        if rng.random() > EVENT_HOURLY_TRIGGER_CHANCE:
            continue

        event = await trigger_random_event(owner.discord_id, rng)
        if event is not None:
            if owner.discord_id not in triggered_events:
                triggered_events[owner.discord_id] = []
            triggered_events[owner.discord_id].append(event)

    logger.info(f"Hourly event check complete. {len(triggered_events)} owners received owner_events.")

    return triggered_events


async def _owner_passes_filter(owner_discord_id: int, filter_spec: dict[str, Any] | None) -> bool:
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False

    from database.session import session_scope

    async with session_scope() as session:
        return await check_owner_event_filter(session, owner_discord_id, filter_spec or {})


async def _create_event_context(owner_discord_id: int, event: Event, rng: random.Random) -> EventContext:
    """
    Create context for an event based on its requirements.

    This pre-selects contextual targets for actions that use the `selected` selector.
    Random targets are resolved when the action executes so they can respect action filters.
    """

    context = EventContext(owner_discord_id=owner_discord_id)

    from database.session import session_scope

    async with session_scope() as session:
        candidate_kennel_ids = await get_matching_kennel_ids_for_owner(session, owner_discord_id, {})
        candidate_pooch_ids = await get_matching_pooch_ids_for_owner(session, owner_discord_id, {})
        context.extra_data["candidate_kennel_ids"] = candidate_kennel_ids
        context.extra_data["candidate_pooch_ids"] = candidate_pooch_ids

        def _uses_selected_selector(action: EventAction, field_name: str) -> bool:
            if action.target_type not in {"pooch", "kennel"}:
                return False
            selector = action.parameters.get(field_name)
            return isinstance(selector, str) and selector.strip().lower() == "selected"

        needs_selected_pooch = False
        needs_selected_kennel = False

        for action in event.actions:
            needs_selected_pooch = needs_selected_pooch or _uses_selected_selector(action, "pooch")
            needs_selected_kennel = needs_selected_kennel or _uses_selected_selector(action, "kennel")

        for option in event.options:
            for action in option.actions:
                needs_selected_pooch = needs_selected_pooch or _uses_selected_selector(action, "pooch")
                needs_selected_kennel = needs_selected_kennel or _uses_selected_selector(action, "kennel")
            for outcome in option.outcomes:
                for action in outcome.actions:
                    needs_selected_pooch = needs_selected_pooch or _uses_selected_selector(action, "pooch")
                    needs_selected_kennel = needs_selected_kennel or _uses_selected_selector(action, "kennel")

        default_pooch_filter = None
        if event.filter.get("pooches"):
            first_filter = event.filter["pooches"][0]
            if isinstance(first_filter, dict):
                default_pooch_filter = {
                    key: value
                    for key, value in first_filter.items()
                    if key not in {"min_count", "max_count", "description"}
                }

        default_kennel_filter = None
        if event.filter.get("kennels"):
            first_filter = event.filter["kennels"][0]
            if isinstance(first_filter, dict):
                default_kennel_filter = {
                    key: value
                    for key, value in first_filter.items()
                    if key not in {"min_count", "max_count", "description"}
                }

        if needs_selected_pooch:
            context.selected_pooch_id = await get_random_matching_pooch_id_for_owner(
                session,
                owner_discord_id,
                default_pooch_filter or {},
                rng,
            )

        if needs_selected_kennel:
            context.selected_kennel_id = await get_random_matching_kennel_id_for_owner(
                session,
                owner_discord_id,
                default_kennel_filter or {},
                rng,
            )

    return context


async def _execute_single_action(
    owner_discord_id: int, action: EventAction, context: EventContext, rng: random.Random
) -> EventResult:
    """
    Execute a single event action.
    """

    def _get_amount_from_params(params: dict[str, Any], rng: random.Random) -> int:
        if "min_amount" in params and "max_amount" in params:
            return rng.randint(int(params["min_amount"]), int(params["max_amount"]))
        return int(params.get("amount", 0))

    async def _get_target_pooch_ids(target_type: str, context: EventContext, params: dict[str, Any]) -> list[int]:
        from database.session import session_scope

        action_filter = params.get("filter", {})
        async with session_scope() as session:
            if target_type == "pooch":
                selector = params.get("pooch")
                if isinstance(selector, str):
                    selector = selector.strip().lower()
                    if selector == "selected":
                        return [context.selected_pooch_id] if context.selected_pooch_id else []
                    if selector == "random":
                        pooch_id = await get_random_matching_pooch_id_for_owner(
                            session,
                            owner_discord_id,
                            action_filter if isinstance(action_filter, dict) else {},
                            rng,
                        )
                        return [pooch_id] if pooch_id is not None else []
                return []

            if target_type == "all_pooches":
                return await get_matching_pooch_ids_for_owner(
                    session,
                    owner_discord_id,
                    action_filter if isinstance(action_filter, dict) else {},
                )

        return []

    async def _get_target_kennel_ids(target_type: str, context: EventContext, params: dict[str, Any]) -> list[int]:
        from database.session import session_scope

        action_filter = params.get("filter", {})
        async with session_scope() as session:
            if target_type == "kennel":
                selector = params.get("kennel")
                if isinstance(selector, str):
                    selector = selector.strip().lower()
                    if selector == "selected":
                        return [context.selected_kennel_id] if context.selected_kennel_id else []
                    if selector == "random":
                        kennel_id = await get_random_matching_kennel_id_for_owner(
                            session,
                            owner_discord_id,
                            action_filter if isinstance(action_filter, dict) else {},
                            rng,
                        )
                        return [kennel_id] if kennel_id is not None else []
                return []

            if target_type == "all_kennels":
                return await get_matching_kennel_ids_for_owner(
                    session,
                    owner_discord_id,
                    action_filter if isinstance(action_filter, dict) else {},
                )

        return []

    result = EventResult()
    action_type = action.action_type
    target_type = action.target_type
    params = action.parameters

    try:
        if action_type == "modify_money":
            amount = _get_amount_from_params(params, rng)
            await give_money_to_owner(owner_discord_id, amount)
            result.money_changed = amount
            result.message = f"{amount:+d} dollars"

        elif action_type == "modify_bloodskulls":
            amount = _get_amount_from_params(params, rng)
            await give_bloodskulls_to_owner(owner_discord_id, amount)
            result.bloodskulls_changed = amount
            result.message = f"{amount:+d} bloodskulls"

        elif action_type == "modify_pooch_health":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            amount = _get_amount_from_params(params, rng)
            for pooch_id in pooch_ids:
                pooch = await modify_pooch_base_health(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("health_changes", {})[pooch_id] = amount

        elif action_type == "modify_pooch_age":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            amount = _get_amount_from_params(params, rng)
            for pooch_id in pooch_ids:
                pooch = await modify_pooch_age(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("age_changes", {})[pooch_id] = amount

        elif action_type == "kill_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            for pooch_id in pooch_ids:
                pooch = await set_pooch_dead(pooch_id)
                if pooch:
                    result.pooches_killed.append(pooch_id)
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = "A pooch has died!" if count == 1 else f"{count} pooches have died!"

        elif action_type == "add_mutation":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            mutation_id = params.get("mutation_id")
            for pooch_id in pooch_ids:
                if mutation_id:
                    await add_mutation_to_pooch(pooch_id, int(mutation_id))
                else:
                    await add_mutation_to_pooch(pooch_id, rng=rng)
                result.pooches_affected.append(pooch_id)

        elif action_type == "remove_mutation":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            mutation_id = params.get("mutation_id")
            for pooch_id in pooch_ids:
                if mutation_id:
                    removed = await remove_mutation_from_pooch(pooch_id, int(mutation_id))
                else:
                    removed = await remove_random_mutation_from_pooch(pooch_id, rng=rng)
                if removed:
                    result.mutations_removed.append((pooch_id, removed.mutation_id))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "add_breed":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            breed_id = params.get("breed_id")
            weight = params.get("weight", 0.5)
            for pooch_id in pooch_ids:
                if breed_id:
                    await add_breed_to_pooch(pooch_id, int(breed_id), weight=weight)
                else:
                    await add_breed_to_pooch(pooch_id, rng=rng, weight=weight)
                result.pooches_affected.append(pooch_id)

        elif action_type == "transfer_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            new_owner_id = params.get("new_owner_discord_id")
            vendor_id = params.get("vendor_id")
            for pooch_id in pooch_ids:
                if new_owner_id:
                    await transfer_pooch_to_owner(pooch_id, int(new_owner_id))
                elif vendor_id:
                    await transfer_pooch_to_vendor(pooch_id, int(vendor_id))
                result.pooches_affected.append(pooch_id)

        elif action_type == "set_breeding_cooldown":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            cooldown = params.get("cooldown", 0)
            if isinstance(cooldown, str) and cooldown.strip().lower() == "base":
                cooldown = 2
            for pooch_id in pooch_ids:
                await set_pooch_breeding_cooldown(pooch_id, int(cooldown))
                result.pooches_affected.append(pooch_id)

        elif action_type == "rename_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, context, params)
            new_name = params.get("name")
            if new_name:
                for pooch_id in pooch_ids:
                    await rename_pooch(pooch_id, str(new_name))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "modify_kennel_capacity":
            kennel_ids = await _get_target_kennel_ids(target_type, context, params)
            amount = _get_amount_from_params(params, rng)
            for kennel_id in kennel_ids:
                kennel = await modify_kennel_pooch_limit(kennel_id, amount)
                if kennel:
                    if kennel_id not in context.affected_kennel_ids:
                        context.affected_kennel_ids.append(kennel_id)
                    result.extra_data.setdefault("kennel_capacity_changes", {})[kennel_id] = amount

        elif action_type == "create_pooch":
            create_pooch_kwargs: dict[str, Any] = {
                "owner_discord_id": owner_discord_id,
                "rng": rng,
            }
            if "name" in params:
                create_pooch_kwargs["name"] = params["name"]
            if "sex" in params:
                create_pooch_kwargs["sex"] = params["sex"]
            if "age" in params:
                create_pooch_kwargs["age"] = params["age"]
            if "base_health" in params:
                create_pooch_kwargs["base_health"] = params["base_health"]
            if "breeding_cooldown" in params:
                create_pooch_kwargs["breeding_cooldown"] = params["breeding_cooldown"]

            pooch = await create_pooch(**create_pooch_kwargs)
            if pooch:
                context.selected_pooch_id = pooch.id
                candidate_pooch_ids = context.extra_data.setdefault("candidate_pooch_ids", [])
                if isinstance(candidate_pooch_ids, list) and pooch.id not in candidate_pooch_ids:
                    candidate_pooch_ids.append(pooch.id)
                if pooch.id not in context.affected_pooch_ids:
                    context.affected_pooch_ids.append(pooch.id)
                result.pooches_created.append(pooch.id)
                result.pooches_affected.append(pooch.id)
                result.message = "A new pooch has appeared!"

        elif action_type == "start_event":
            if bool(params.get("random_event", False)):
                started_event = await trigger_random_event(owner_discord_id, rng=rng)
            else:
                event_name = params.get("event")
                event = await db_get_owner_event_by_name(event_name.strip())
                if event is None:
                    logger.warning(f"Unknown event '{event_name}' triggered. Skipping...")
                    started_events = result.extra_data.setdefault("started_events", [])
                    result.message = "Error starting followup event."
                    return result
                started_event = await trigger_specific_event(owner_discord_id, event.id, rng=rng)

            if started_event is not None:
                started_events = result.extra_data.setdefault("started_events", [])
                started_events.append(
                    {
                        "active_owner_event_id": started_event.active_owner_event_id,
                        "event_id": started_event.event_id,
                        "name": started_event.name,
                    }
                )
                result.message = f"Started event '{started_event.name}'."

        else:
            logger.warning(f"Unknown action type: {action_type}")

    except Exception as e:
        logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
        result.success = False
        result.message = f"Error: {str(e)}"

    return result


async def _execute_event_actions(
    owner_discord_id: int, actions: list[EventAction], context: EventContext, rng: random.Random
) -> EventResult:
    """
    Execute a list of event actions.
    """

    result = EventResult()

    for action in sorted(actions, key=lambda a: a.action_order):
        action_result = await _execute_single_action(owner_discord_id, action, context, rng)
        result.merge(action_result)

    return result


async def _create_and_execute_event(
    owner_discord_id: int, event: Event, rng: random.Random
) -> Optional[TriggeredEvent]:
    """
    Create an active event and execute it if it doesn't require a response.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    event: Event
        The event to trigger.

    rng: Random
        Random number generator.

    Returns
    -------
    TriggeredEvent, optional
        The triggered event, or None if creation failed.
    """

    context = await _create_event_context(owner_discord_id, event, rng)

    expires_at = None
    if event.requires_response:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=event.response_timeout)

    active_event = await create_active_owner_event(
        event_id=event.id,
        owner_discord_id=owner_discord_id,
        context=context.to_dict(),
        expires_at=expires_at,
    )

    if active_event is None:
        logger.error(f"Failed to create active event for owner {owner_discord_id}")
        return None

    logger.info(f"Triggered event '{event.name}' for owner {owner_discord_id}")

    # Event-level actions always fire immediately at trigger time (before the user picks)
    result = await _execute_event_actions(owner_discord_id, event.actions, context, rng)
    await update_active_event_result(active_event.id, result.to_dict())

    if not event.requires_response:
        await archive_active_event(active_event.id)

    active_event.result_summary = result.to_dict()
    active_event.context = context.to_dict()
    active_event.expires_at = expires_at
    return await to_triggered_event(active_event)


async def trigger_random_event(owner_discord_id: int, rng: Optional[random.Random] = None) -> Optional[TriggeredEvent]:
    """
    Attempt to trigger a random event for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    rng: Random, optional
        Random number generator for reproducibility.

    Returns
    -------
    TriggeredEvent, optional
        The triggered event, or None if no event was triggered.
    """

    if rng is None:
        rng = random.Random()

    # Check if owner already has too many active events
    active_events = await list_active_owner_events_for_owner(owner_discord_id, pending_only=True)
    if len(active_events) >= EVENT_MAX_ACTIVE_PER_OWNER:
        logger.debug(f"Owner {owner_discord_id} has max active events, skipping trigger...")
        return None

    selected_event = await get_random_eligible_owner_event_for_owner(owner_discord_id, rng=rng)

    if selected_event is None:
        logger.debug(f"No eligible events for owner {owner_discord_id}.")
        return None

    return await _create_and_execute_event(owner_discord_id, selected_event, rng)


async def trigger_specific_event(
    owner_discord_id: int, event_id: int, rng: Optional[random.Random] = None
) -> Optional[TriggeredEvent]:
    """
    Trigger a specific event for an owner (for testing or admin purposes).

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    event_id: int
        The ID of the event to trigger.

    rng: Random, optional
        Random number generator for reproducibility.

    Returns
    -------
    TriggeredEvent, optional
        The triggered event, or None if the event couldn't be triggered.
    """

    if rng is None:
        rng = random.Random()

    event = await db_get_owner_event_by_id(event_id)
    if event is None:
        logger.warning(f"Event {event_id} not found")
        return None

    return await _create_and_execute_event(owner_discord_id, event, rng)
