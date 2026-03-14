import logging
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from src.database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    add_pooch_breeds,
    add_pooch_to_kennel,
    add_pooch_to_vendor_stock,
    archive_active_event,
    bury_pooch,
    check_owner_event_filter_for_owner,
    create_active_owner_event,
    create_pooch,
    damn_pooch,
    get_active_owner_event_by_id,
    get_owner_by_discord_id,
)
from src.database import get_owner_event_by_id as db_get_owner_event_by_id
from src.database import get_owner_event_by_name as db_get_owner_event_by_name
from src.database import (
    get_owner_event_option_by_id,
    get_pending_active_owner_event,
    get_pooch_by_id,
    get_pooch_kennel,
    get_random_eligible_owner_event_for_owner,
    get_random_matching_kennel_id,
    get_random_matching_pooch_id,
    give_bloodskulls_to_owner,
    give_money_to_owner,
    list_active_owner_events_for_owner,
)
from src.database import list_all_owner_events as db_list_all_owner_events
from src.database import (
    list_expired_active_owner_events,
    list_kennels_for_owner,
    list_matching_kennel_ids,
    list_matching_pooch_ids,
    list_matching_pooch_ids_in_kennel,
    list_owner_event_history_for_owner,
    list_owners,
    list_pooch_breed_weights,
    list_pooch_mutations,
    list_pooches_for_kennel,
    list_servers_for_owner,
    list_vendor_pooch_stock,
    list_vendors,
    modify_kennel_pooch_limit,
    modify_pooch_age,
    modify_pooch_base_health,
    remove_mutation_from_pooch,
    remove_pooch_from_kennel,
    remove_pooch_from_vendor_stock,
    remove_random_mutation_from_pooch,
    rename_pooch,
    respond_to_active_owner_event,
    set_pooch_breeding_cooldown,
    set_pooch_dead,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
    update_active_event_result,
)

from .breeding import breed_pooches
from .constants import (
    EVENT_HOURLY_TRIGGER_CHANCE,
    EVENT_MAX_ACTIVE_PER_OWNER,
    POOCH_BREEDING_COOLDOWN,
)
from .manage_vendors import get_pooch_buy_price, get_pooch_sell_price
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
from .utils import get_pooch_mutation_advanced_option_total

if TYPE_CHECKING:
    from src.database.models import Event as EventDB
    from src.database.models import EventAction, EventOption, EventOutcome


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

    if not await check_owner_event_filter_for_owner(owner_discord_id, option.filter):
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


async def _create_event_context(owner_discord_id: int, event: EventDB, rng: random.Random) -> EventContext:
    """
    Create context for an event based on its requirements.

    This pre-selects contextual targets for actions that use the `selected` selector.
    Random targets are resolved when the action executes so they can respect action filters.
    """

    context = EventContext(owner_discord_id=owner_discord_id)

    candidate_kennel_ids = await list_matching_kennel_ids(owner_discord_id, {})
    candidate_pooch_ids = await list_matching_pooch_ids(owner_discord_id, {})
    context.extra_data["candidate_kennel_ids"] = candidate_kennel_ids
    context.extra_data["candidate_pooch_ids"] = candidate_pooch_ids

    def _uses_selected_selector(action: EventAction) -> tuple[bool, bool]:
        selector = action.parameters.get("selector")
        if not isinstance(selector, str) or selector.strip().lower() != "selected":
            return False, False
        return action.target_type == "pooch", action.target_type == "kennel"

    needs_selected_pooch = False
    needs_selected_kennel = False

    for action in event.actions:
        p, k = _uses_selected_selector(action)
        needs_selected_pooch = needs_selected_pooch or p
        needs_selected_kennel = needs_selected_kennel or k

    for option in event.options:
        for action in option.actions:
            p, k = _uses_selected_selector(action)
            needs_selected_pooch = needs_selected_pooch or p
            needs_selected_kennel = needs_selected_kennel or k
        for outcome in option.outcomes:
            for action in outcome.actions:
                p, k = _uses_selected_selector(action)
                needs_selected_pooch = needs_selected_pooch or p
                needs_selected_kennel = needs_selected_kennel or k

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
        context.selected_pooch_id = await get_random_matching_pooch_id(
            owner_discord_id,
            default_pooch_filter or {},
            rng,
        )

    if needs_selected_kennel:
        context.selected_kennel_id = await get_random_matching_kennel_id(
            owner_discord_id,
            default_kennel_filter or {},
            rng,
        )

    return context


async def _deliver_pooch(owner_discord_id: int, pooch_id: int, destination: str) -> tuple[str, Optional[str]]:
    """
    Deliver a pooch to a destination. Returns (destination_key, kennel_name_or_None).

    Destinations: "kennel" | "graveyard" | "hell" | "town"
    For "kennel", places in the first kennel with free space. If no kennel has space, falls back to "town".
    """

    destination = destination.strip().lower() if isinstance(destination, str) else "town"

    if destination == "kennel":
        kennels = await list_kennels_for_owner(owner_discord_id)
        for kennel in kennels:
            pooches_in_kennel = await list_pooches_for_kennel(kennel.id)
            if len(pooches_in_kennel) < kennel.pooch_limit:
                await add_pooch_to_kennel(kennel.id, pooch_id)
                return "kennel", kennel.name
        # No kennel with free space — fall through to town
        return "town", None

    elif destination == "graveyard":
        await bury_pooch(owner_discord_id, pooch_id)
        return "graveyard", None

    elif destination == "hell":
        await damn_pooch(pooch_id)
        return "hell", None

    else:  # "town" or unknown
        return "town", None


async def _execute_single_action(
    owner_discord_id: int, action: EventAction, context: EventContext, rng: random.Random
) -> EventResult:
    """
    Execute a single event action.
    """

    def _get_amount_from_parameters(parameters: dict[str, Any], rng: random.Random) -> int:
        if "min_amount" in parameters and "max_amount" in parameters:
            return rng.randint(parameters["min_amount"], parameters["max_amount"])
        return parameters.get("amount", 0)

    def _resolve_amount(parameters: dict[str, Any], rng: random.Random) -> tuple[int | None, bool]:
        """Return (pre_rolled_amount_or_None, roll_once). If roll_once, the amount is already rolled."""
        roll_once = bool(parameters.get("roll_once", False))
        if roll_once:
            return _get_amount_from_parameters(parameters, rng), True
        return None, False

    async def _get_target_pooch_ids(target_type: str, selector: str, parameters: dict[str, Any]) -> list[int]:
        action_filter = parameters.get("filter", {})
        filter_spec = action_filter if isinstance(action_filter, dict) else {}
        count_param = parameters.get("count")
        count = int(count_param) if isinstance(count_param, int) and count_param > 0 else None

        # use_saved: pull IDs from a named slot
        use_saved = parameters.get("use_saved")
        if isinstance(use_saved, str) and use_saved:
            slot = context.extra_data.get(use_saved, {})
            if not isinstance(slot, dict):
                return []
            if target_type == "kennel":
                # Slot stores kennel_ids; enumerate pooches within those kennels
                saved_kennel_ids = list(slot.get("kennel_ids", []))
                pooch_filter_raw = parameters.get("pooch_filter", {})
                pooch_filter = pooch_filter_raw if isinstance(pooch_filter_raw, dict) else {}
                pooch_ids: list[int] = []
                for kid in saved_kennel_ids:
                    pooch_ids.extend(await list_matching_pooch_ids_in_kennel(owner_discord_id, kid, pooch_filter))
                return pooch_ids
            return list(slot.get("pooch_ids", []))

        if target_type == "owner":
            pooch_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
        elif target_type == "pooch":
            if selector == "selected":
                pooch_ids = [context.selected_pooch_id] if context.selected_pooch_id else []
            elif selector == "random":
                all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
                if count is not None:
                    pooch_ids = rng.sample(all_ids, min(count, len(all_ids))) if all_ids else []
                else:
                    pooch_ids = [rng.choice(all_ids)] if all_ids else []
            elif selector == "all":
                pooch_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
            elif selector == "random_exclude":
                all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
                if count is not None and count < len(all_ids):
                    excluded = set(rng.sample(all_ids, count))
                    pooch_ids = [pid for pid in all_ids if pid not in excluded]
                else:
                    pooch_ids = []
            else:
                pooch_ids = []
        else:
            # target_type == "kennel": resolve kennel(s), then return all pooches in them
            kennel_filter = filter_spec
            pooch_filter_raw = parameters.get("pooch_filter", {})
            pooch_filter = pooch_filter_raw if isinstance(pooch_filter_raw, dict) else {}

            if selector == "selected":
                kennel_ids = [context.selected_kennel_id] if context.selected_kennel_id else []
            elif selector == "random":
                all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, kennel_filter)
                if count is not None:
                    kennel_ids = rng.sample(all_kennel_ids, min(count, len(all_kennel_ids))) if all_kennel_ids else []
                else:
                    kennel_id = await get_random_matching_kennel_id(owner_discord_id, kennel_filter, rng)
                    kennel_ids = [kennel_id] if kennel_id is not None else []
            elif selector == "all":
                kennel_ids = await list_matching_kennel_ids(owner_discord_id, kennel_filter)
            elif selector == "random_exclude":
                all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, kennel_filter)
                if count is not None and count < len(all_kennel_ids):
                    excluded = set(rng.sample(all_kennel_ids, count))
                    kennel_ids = [kid for kid in all_kennel_ids if kid not in excluded]
                else:
                    kennel_ids = []
            else:
                kennel_ids = []

            pooch_ids = []
            for kennel_id in kennel_ids:
                pooch_ids.extend(await list_matching_pooch_ids_in_kennel(owner_discord_id, kennel_id, pooch_filter))

        # save_as: store resolved IDs (and optionally kennel IDs) into a named slot
        save_as = parameters.get("save_as")
        if isinstance(save_as, str) and save_as:
            slot: dict[str, Any] = {"pooch_ids": pooch_ids}
            if parameters.get("save_kennel"):
                kennel_ids_for_slot: list[int] = []
                for pid in pooch_ids:
                    kennel = await get_pooch_kennel(pid)
                    if kennel is not None and kennel.id not in kennel_ids_for_slot:
                        kennel_ids_for_slot.append(kennel.id)
                slot["kennel_ids"] = kennel_ids_for_slot
            context.extra_data[save_as] = slot

        return pooch_ids

    async def _get_target_kennel_ids(target_type: str, selector: str, parameters: dict[str, Any]) -> list[int]:
        action_filter = parameters.get("filter", {})
        filter_spec = action_filter if isinstance(action_filter, dict) else {}
        count_param = parameters.get("count")
        count = int(count_param) if isinstance(count_param, int) and count_param > 0 else None

        # use_saved: pull kennel IDs from a named slot
        use_saved = parameters.get("use_saved")
        if isinstance(use_saved, str) and use_saved:
            slot = context.extra_data.get(use_saved, {})
            return list(slot.get("kennel_ids", [])) if isinstance(slot, dict) else []

        if target_type == "owner":
            kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
        elif selector == "selected":
            kennel_ids = [context.selected_kennel_id] if context.selected_kennel_id else []
        elif selector == "random":
            all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
            if count is not None:
                kennel_ids = rng.sample(all_kennel_ids, min(count, len(all_kennel_ids))) if all_kennel_ids else []
            else:
                kennel_id = await get_random_matching_kennel_id(owner_discord_id, filter_spec, rng)
                kennel_ids = [kennel_id] if kennel_id is not None else []
        elif selector == "all":
            kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
        elif selector == "random_exclude":
            all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
            if count is not None and count < len(all_kennel_ids):
                excluded = set(rng.sample(all_kennel_ids, count))
                kennel_ids = [kid for kid in all_kennel_ids if kid not in excluded]
            else:
                kennel_ids = []
        else:
            kennel_ids = []

        # save_as: store resolved kennel IDs into a named slot
        save_as = parameters.get("save_as")
        if isinstance(save_as, str) and save_as:
            context.extra_data[save_as] = {"kennel_ids": kennel_ids}

        return kennel_ids

    result = EventResult()
    action_type = action.action_type
    target_type = action.target_type
    parameters = action.parameters

    # Resolve selector (default to "random")
    raw_selector = parameters.get("selector", "random")
    selector = str(raw_selector).strip().lower() if isinstance(raw_selector, str) else "random"

    try:
        # Owner Actions
        if action_type == "modify_money":
            amount = _get_amount_from_parameters(parameters, rng)
            await give_money_to_owner(owner_discord_id, amount)
            result.money_changed = amount
            result.message = f"{amount:+d} dollars"

        elif action_type == "modify_bloodskulls":
            amount = _get_amount_from_parameters(parameters, rng)
            await give_bloodskulls_to_owner(owner_discord_id, amount)
            result.bloodskulls_changed = amount
            result.message = f"{amount:+d} bloodskulls"

        elif action_type == "create_pooch":
            create_pooch_kwargs: dict[str, Any] = {
                "owner_discord_id": owner_discord_id,
                "rng": rng,
            }
            if "name" in parameters:
                create_pooch_kwargs["name"] = parameters["name"]
            if "sex" in parameters:
                create_pooch_kwargs["sex"] = parameters["sex"]
            if "age" in parameters:
                create_pooch_kwargs["age"] = parameters["age"]
            if "base_health" in parameters:
                create_pooch_kwargs["base_health"] = parameters["base_health"]
            if "breeding_cooldown" in parameters:
                create_pooch_kwargs["breeding_cooldown"] = parameters["breeding_cooldown"]

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

                destination_str = parameters.get("destination", "town")
                dest_key, kennel_name = await _deliver_pooch(owner_discord_id, pooch.id, destination_str)
                if dest_key == "kennel":
                    result.message = f"A new pooch has appeared and was placed in {kennel_name}!"
                elif dest_key == "graveyard":
                    result.message = "A new pooch has appeared and was placed in the graveyard!"
                elif dest_key == "hell":
                    result.message = "A new pooch has appeared and was sent to Hell!"
                else:
                    result.message = "A new pooch has appeared!"

                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as:
                    context.extra_data[save_as] = {"pooch_ids": [pooch.id]}

        elif action_type == "clone_pooch":
            # Resolve the source pooch
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            source_id = pooch_ids[0] if pooch_ids else None
            if source_id is None:
                logger.warning("clone_pooch: could not resolve source pooch; skipping")
            else:
                source = await get_pooch_by_id(source_id)
                if source is None:
                    logger.warning(f"clone_pooch: source pooch {source_id} not found; skipping")
                else:
                    clone_kwargs: dict[str, Any] = {
                        "owner_discord_id": owner_discord_id,
                        "rng": rng,
                        "name": parameters.get("name", source.name),
                        "sex": parameters.get("sex", source.sex),
                        "age": parameters.get("age", source.age),
                        "base_health": parameters.get("base_health", source.base_health),
                        "breeding_cooldown": parameters.get("breeding_cooldown", source.breeding_cooldown),
                    }
                    clone = await create_pooch(**clone_kwargs)
                    if clone:
                        # Copy breeds (raw integer weights) and mutations from source
                        breed_weights = await list_pooch_breed_weights(source_id)
                        if breed_weights:
                            await add_pooch_breeds(clone.id, dict(breed_weights))
                        for mutation in await list_pooch_mutations(source_id):
                            await add_mutation_to_pooch(clone.id, mutation_id=mutation.id)

                        context.selected_pooch_id = clone.id
                        candidate_pooch_ids = context.extra_data.setdefault("candidate_pooch_ids", [])
                        if isinstance(candidate_pooch_ids, list) and clone.id not in candidate_pooch_ids:
                            candidate_pooch_ids.append(clone.id)
                        if clone.id not in context.affected_pooch_ids:
                            context.affected_pooch_ids.append(clone.id)
                        result.pooches_created.append(clone.id)
                        result.pooches_affected.append(clone.id)

                        destination_str = parameters.get("destination", "town")
                        dest_key, kennel_name = await _deliver_pooch(owner_discord_id, clone.id, destination_str)
                        if dest_key == "kennel":
                            result.message = f"A clone of {source.name} appeared and was placed in {kennel_name}!"
                        elif dest_key == "graveyard":
                            result.message = f"A clone of {source.name} appeared and was placed in the graveyard!"
                        elif dest_key == "hell":
                            result.message = f"A clone of {source.name} appeared and was sent to Hell!"
                        else:
                            result.message = f"A clone of {source.name} has appeared!"

                        # save_as: supports "source" or "clone" (or plain string → clone)
                        save_as_raw = parameters.get("save_as")
                        if save_as_raw is not None:
                            save_specs: list[dict[str, str]]
                            if isinstance(save_as_raw, str):
                                save_specs = [{"slot": save_as_raw, "target": "clone"}]
                            elif isinstance(save_as_raw, list):
                                save_specs = [s for s in save_as_raw if isinstance(s, dict)]
                            else:
                                save_specs = []
                            for spec in save_specs:
                                slot = spec.get("slot")
                                target = spec.get("target", "clone")
                                if not isinstance(slot, str) or not slot:
                                    continue
                                if target == "source":
                                    context.extra_data[slot] = {"pooch_ids": [source_id]}
                                else:  # "clone"
                                    context.extra_data[slot] = {"pooch_ids": [clone.id]}

        # Kennel Actions
        elif action_type == "modify_kennel_capacity":
            kennel_ids = await _get_target_kennel_ids(target_type, selector, parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            for kennel_id in kennel_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                kennel = await modify_kennel_pooch_limit(kennel_id, amount)
                if kennel:
                    if kennel_id not in context.affected_kennel_ids:
                        context.affected_kennel_ids.append(kennel_id)
                    result.extra_data.setdefault("kennel_capacity_changes", {})[kennel_id] = amount

        # Pooch Actions
        elif action_type == "modify_pooch_health":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            for pooch_id in pooch_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                pooch = await modify_pooch_base_health(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("health_changes", {})[pooch_id] = amount

        elif action_type == "modify_pooch_age":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            for pooch_id in pooch_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                pooch = await modify_pooch_age(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("age_changes", {})[pooch_id] = amount

        elif action_type == "kill_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            for pooch_id in pooch_ids:
                pooch = await set_pooch_dead(pooch_id)
                if pooch:
                    result.pooches_killed.append(pooch_id)
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = "A pooch has died!" if count == 1 else f"{count} pooches have died!"

        elif action_type == "add_mutation":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            mutation_id = parameters.get("mutation_id")
            for pooch_id in pooch_ids:
                if mutation_id:
                    await add_mutation_to_pooch(pooch_id, mutation_id)
                else:
                    await add_mutation_to_pooch(pooch_id, rng=rng)
                result.pooches_affected.append(pooch_id)

        elif action_type == "remove_mutation":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            mutation_id = parameters.get("mutation_id")
            for pooch_id in pooch_ids:
                if mutation_id:
                    removed = await remove_mutation_from_pooch(pooch_id, mutation_id)
                else:
                    removed = await remove_random_mutation_from_pooch(pooch_id, rng=rng)
                if removed:
                    result.mutations_removed.append((pooch_id, removed.mutation_id))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "add_breed":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            breed_id = parameters.get("breed_id")
            weight = parameters.get("weight", 0.5)
            for pooch_id in pooch_ids:
                if breed_id:
                    await add_breed_to_pooch(pooch_id, breed_id, weight=weight)
                else:
                    await add_breed_to_pooch(pooch_id, rng=rng, weight=weight)
                result.pooches_affected.append(pooch_id)

        elif action_type == "transfer_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            new_owner_id = parameters.get("new_owner_discord_id")
            vendor_id = parameters.get("vendor_id")
            for pooch_id in pooch_ids:
                if new_owner_id:
                    await transfer_pooch_to_owner(pooch_id, new_owner_id)
                elif vendor_id:
                    await transfer_pooch_to_vendor(pooch_id, vendor_id)
                result.pooches_affected.append(pooch_id)

        elif action_type == "set_breeding_cooldown":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            cooldown = parameters.get("cooldown", 0)
            for pooch_id in pooch_ids:
                if isinstance(cooldown, str) and cooldown.strip().lower() == "base":
                    resolved_cooldown = max(
                        POOCH_BREEDING_COOLDOWN
                        + await get_pooch_mutation_advanced_option_total(pooch_id, "breeding_cooldown"),
                        0,
                    )
                else:
                    resolved_cooldown = cooldown
                await set_pooch_breeding_cooldown(pooch_id, resolved_cooldown)
                result.pooches_affected.append(pooch_id)

        elif action_type == "rename_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            new_name = parameters.get("name")
            if new_name:
                for pooch_id in pooch_ids:
                    await rename_pooch(pooch_id, str(new_name))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "breed_pooches":
            raw_first_selector = parameters.get("first_selector", "random")
            first_selector = (
                str(raw_first_selector).strip().lower() if isinstance(raw_first_selector, str) else "random"
            )
            raw_second_selector = parameters.get("second_selector", "random")
            second_selector = (
                str(raw_second_selector).strip().lower() if isinstance(raw_second_selector, str) else "random"
            )

            first_filter_raw = parameters.get("first_filter", {})
            first_filter = first_filter_raw if isinstance(first_filter_raw, dict) else {}
            second_filter_raw = parameters.get("second_filter", {})
            second_filter = second_filter_raw if isinstance(second_filter_raw, dict) else {}

            async def _resolve_breed_pooch_id(sel: str, filt: dict) -> int | None:
                if sel == "selected":
                    return context.selected_pooch_id
                elif sel == "random":
                    return await get_random_matching_pooch_id(owner_discord_id, filt, rng)
                elif sel == "all":
                    ids = await list_matching_pooch_ids(owner_discord_id, filt)
                    return rng.choice(ids) if ids else None
                return None

            require_unique = bool(parameters.get("require_unique", True))
            require_same = bool(parameters.get("require_same", False))

            first_pooch_id = await _resolve_breed_pooch_id(first_selector, first_filter)
            if require_same:
                second_pooch_id = first_pooch_id
            else:
                second_pooch_id = await _resolve_breed_pooch_id(second_selector, second_filter)

            if first_pooch_id is None or second_pooch_id is None:
                logger.warning("breed_pooches: could not resolve one or both pooches; skipping")
            elif require_unique and first_pooch_id == second_pooch_id:
                logger.warning(
                    "breed_pooches: require_unique is set but both selectors resolved to the same pooch; skipping"
                )
            else:
                try:
                    baby_ids = await breed_pooches(
                        first_pooch_id, second_pooch_id, rng_seed=rng.randint(0, 2**31), skip_validation=True
                    )
                    result.pooches_created.extend(baby_ids)
                    result.pooches_affected.extend(baby_ids)

                    for baby_id in baby_ids:
                        if "baby_name" in parameters:
                            await rename_pooch(baby_id, str(parameters["baby_name"]))
                        if "baby_age" in parameters:
                            await modify_pooch_age(baby_id, parameters["baby_age"])
                        if "baby_base_health" in parameters:
                            await modify_pooch_base_health(baby_id, parameters["baby_base_health"])
                        if "baby_breeding_cooldown" in parameters:
                            await set_pooch_breeding_cooldown(baby_id, parameters["baby_breeding_cooldown"])

                    count = len(baby_ids)
                    result.message = "A puppy was born!" if count == 1 else f"{count} puppies were born!"

                    # save_as: supports "first_parent", "second_parent", "baby" (or list of those)
                    # Each save_as entry is a dict: { "slot": str, "target": "first_parent"|"second_parent"|"baby" }
                    # For convenience, a plain string defaults to saving the baby/babies.
                    save_as_raw = parameters.get("save_as")
                    if save_as_raw is not None:
                        save_specs: list[dict[str, str]]
                        if isinstance(save_as_raw, str):
                            save_specs = [{"slot": save_as_raw, "target": "baby"}]
                        elif isinstance(save_as_raw, list):
                            save_specs = [s for s in save_as_raw if isinstance(s, dict)]
                        else:
                            save_specs = []
                        for spec in save_specs:
                            slot = spec.get("slot")
                            target = spec.get("target", "baby")
                            if not isinstance(slot, str) or not slot:
                                continue
                            if target == "first_parent":
                                context.extra_data[slot] = {"pooch_ids": [first_pooch_id]}
                            elif target == "second_parent":
                                context.extra_data[slot] = {"pooch_ids": [second_pooch_id]}
                            else:  # "baby"
                                context.extra_data[slot] = {"pooch_ids": list(baby_ids)}

                except ValueError as e:
                    logger.warning(f"breed_pooches: breeding failed — {e}")

        elif action_type == "sell_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            vendor_id = parameters.get("vendor_id")
            vendor_selector = str(parameters.get("vendor_selector", "random")).strip().lower()
            value_multiplier = parameters.get("value_multiplier")
            multiplier = float(value_multiplier) if isinstance(value_multiplier, (int, float)) else 1.0

            # Resolve vendor if not explicitly specified
            resolved_vendor_id: int | None = vendor_id if isinstance(vendor_id, int) else None
            if resolved_vendor_id is None and vendor_selector == "random":
                servers = await list_servers_for_owner(owner_discord_id)
                all_vendors = []
                for server in servers:
                    all_vendors.extend(await list_vendors(server.discord_id))
                if all_vendors:
                    resolved_vendor_id = rng.choice(all_vendors).id

            for pooch_id in pooch_ids:
                pooch = await get_pooch_by_id(pooch_id)
                if pooch is None or not pooch.alive:
                    continue
                if resolved_vendor_id is not None:
                    price = round((await get_pooch_sell_price(pooch_id, resolved_vendor_id)) * multiplier)
                    await give_money_to_owner(owner_discord_id, price)
                    await transfer_pooch_to_vendor(pooch_id, resolved_vendor_id)
                    await remove_pooch_from_kennel(pooch_id)
                    await add_pooch_to_vendor_stock(resolved_vendor_id, pooch_id)
                    result.money_changed += price
                else:
                    price = round((await get_pooch_sell_price(pooch_id)) * multiplier)
                    await give_money_to_owner(owner_discord_id, price)
                    result.money_changed += price
                result.pooches_affected.append(pooch_id)

        elif action_type == "buy_pooch":
            vendor_id = parameters.get("vendor_id")
            vendor_selector = str(parameters.get("vendor_selector", "random")).strip().lower()
            pooch_selector = str(parameters.get("pooch_selector", "random")).strip().lower()
            pooch_filter_raw = parameters.get("pooch_filter", {})
            pooch_filter = pooch_filter_raw if isinstance(pooch_filter_raw, dict) else {}
            value_multiplier = parameters.get("value_multiplier")
            multiplier = float(value_multiplier) if isinstance(value_multiplier, (int, float)) else 1.0
            destination_str = parameters.get("destination", "kennel")

            # Resolve vendor
            resolved_vendor_id = vendor_id if isinstance(vendor_id, int) else None
            if resolved_vendor_id is None and vendor_selector == "random":
                servers = await list_servers_for_owner(owner_discord_id)
                all_vendors = []
                for server in servers:
                    all_vendors.extend(await list_vendors(server.discord_id))
                if all_vendors:
                    resolved_vendor_id = rng.choice(all_vendors).id

            if resolved_vendor_id is None:
                logger.warning("buy_pooch: no vendor available; skipping")
            else:
                stock = await list_vendor_pooch_stock(resolved_vendor_id)
                if pooch_filter:
                    filter_ids = await list_matching_pooch_ids(owner_discord_id, pooch_filter)
                    stock = [p for p in stock if p.id in set(filter_ids)]
                if not stock:
                    logger.warning("buy_pooch: no pooches available from vendor; skipping")
                else:
                    pooch_db = rng.choice(stock) if pooch_selector == "random" else stock[0]
                    price = round((await get_pooch_buy_price(pooch_db.id, resolved_vendor_id)) * multiplier)
                    owner = await get_owner_by_discord_id(owner_discord_id)
                    if owner is None or owner.dollars < price:
                        logger.warning("buy_pooch: owner cannot afford the pooch; skipping")
                    else:
                        await remove_pooch_from_vendor_stock(resolved_vendor_id, pooch_db.id)
                        await give_money_to_owner(owner_discord_id, -price)
                        await transfer_pooch_to_owner(pooch_db.id, owner_discord_id)

                        dest_key, kennel_name = await _deliver_pooch(owner_discord_id, pooch_db.id, destination_str)
                        result.money_changed -= price
                        result.pooches_created.append(pooch_db.id)
                        result.pooches_affected.append(pooch_db.id)

                        save_as = parameters.get("save_as")
                        if isinstance(save_as, str) and save_as:
                            context.extra_data[save_as] = {"pooch_ids": [pooch_db.id]}

                        if dest_key == "kennel":
                            result.message = f"{pooch_db.name} was purchased and placed in {kennel_name}!"
                        else:
                            result.message = f"{pooch_db.name} was purchased!"

        # Other Actions
        elif action_type == "start_event":
            if bool(parameters.get("random_event", False)):
                started_event = await trigger_random_event(owner_discord_id, rng=rng)
            else:
                event_name = parameters.get("event")
                event = await db_get_owner_event_by_name(event_name.strip())
                if event is None:
                    logger.warning(f"Unknown event '{event_name}' triggered. Skipping...")
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
        repeat = max(int(action.repeat), 1) if isinstance(action.repeat, int) else 1
        for _ in range(repeat):
            action_result = await _execute_single_action(owner_discord_id, action, context, rng)
            result.merge(action_result)

    return result


async def _create_and_execute_event(
    owner_discord_id: int, event: EventDB, rng: random.Random
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
