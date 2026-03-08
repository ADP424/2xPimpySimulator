import logging
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    archive_active_event,
    create_active_event,
    create_pooch,
    get_active_event_by_id,
)
from database import get_event_by_id as db_get_event_by_id
from database import (
    get_event_option_by_id,
    get_owner_by_discord_id,
    get_pending_active_event,
    get_random_eligible_event_for_owner,
    give_bloodskulls_to_owner,
    give_money_to_owner,
    list_active_events_for_owner,
)
from database import list_all_events as db_list_all_events
from database import (
    list_event_history_for_owner,
    list_expired_active_events,
    list_kennels_for_owner,
    list_owners,
    list_pooches_for_kennel,
    modify_kennel_pooch_limit,
    modify_pooch_age,
    modify_pooch_base_health,
    remove_mutation_from_pooch,
    remove_random_mutation_from_pooch,
    rename_pooch,
    respond_to_active_event,
    set_pooch_breeding_cooldown,
    set_pooch_dead,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
    update_active_event_result,
)
from game.constants import (
    EVENT_HOURLY_TRIGGER_CHANCE,
    EVENT_MAX_ACTIVE_PER_OWNER,
)

from .models.events import EventContext, EventResult, TriggeredEvent

if TYPE_CHECKING:
    from database.models import Event, EventAction


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

    active_events = await list_active_events_for_owner(owner_discord_id, pending_only=pending_only)

    result = []
    for active_event in active_events:
        event = active_event.event
        context = EventContext.from_dict(active_event.context)

        options = []
        if event.requires_response:
            for option in sorted(event.options, key=lambda o: o.option_order):
                options.append(
                    {
                        "id": option.id,
                        "label": option.label,
                        "description": option.description,
                        "min_money": option.min_money,
                        "min_bloodskulls": option.min_bloodskulls,
                    }
                )

        triggered = TriggeredEvent(
            active_event_id=active_event.id,
            event_id=event.id,
            name=event.name,
            category=event.category,
            description=event.description,
            flavor_text=event.flavor_text,
            severity=event.severity,
            requires_response=event.requires_response,
            response_timeout=event.response_timeout,
            expires_at=active_event.expires_at,
            context=context,
            options=options,
        )

        if active_event.result_summary:
            triggered.result = EventResult.from_dict(active_event.result_summary)

        result.append(triggered)

    return result


async def get_event_by_id(event_id: int) -> Optional[dict[str, Any]]:
    """
    Get detailed information about an event.

    Parameters
    ----------
    event_id: int
        The ID of the event.

    Returns
    -------
    dict, optional
        Event information, or None if not found.
    """

    event = await db_get_event_by_id(event_id)
    if event is None:
        return None

    return {
        "id": event.id,
        "name": event.name,
        "category": event.category,
        "description": event.description,
        "flavor_text": event.flavor_text,
        "severity": event.severity,
        "rarity": event.rarity,
        "requires_response": event.requires_response,
        "response_timeout": event.response_timeout,
        "min_pooches": event.min_pooches,
        "min_kennels": event.min_kennels,
        "min_money": event.min_money,
        "min_bloodskulls": event.min_bloodskulls,
        "actions": [
            {
                "action_type": action.action_type,
                "target_type": action.target_type,
                "parameters": action.parameters,
            }
            for action in sorted(event.actions, key=lambda a: a.action_order)
        ],
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "description": option.description,
                "min_money": option.min_money,
                "min_bloodskulls": option.min_bloodskulls,
            }
            for option in sorted(event.options, key=lambda o: o.option_order)
        ],
    }


async def get_event_history(owner_discord_id: int, limit: int = 50) -> list[dict[str, Any]]:
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
    list[dict]
        List of event history records.
    """

    history = await list_event_history_for_owner(owner_discord_id, limit)
    return [
        {
            "id": record.id,
            "event_id": record.event_id,
            "context": record.context,
            "result_summary": record.result_summary,
            "triggered_at": record.triggered_at.isoformat(),
            "completed_at": record.completed_at.isoformat(),
            "selected_option_id": record.selected_option_id,
            "timed_out": record.timed_out,
        }
        for record in history
    ]


async def get_pending_event(owner_discord_id: int, active_event_id: Optional[int] = None) -> Optional[TriggeredEvent]:
    """
    Get a specific pending event for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    active_event_id: int, optional
        The specific active event ID to retrieve.

    Returns
    -------
    TriggeredEvent, optional
        The triggered event, or None if not found.
    """

    if active_event_id is not None:
        active_event = await get_active_event_by_id(active_event_id)
        if active_event is None or active_event.owner_discord_id != owner_discord_id:
            return None
        if active_event.responded_at is not None:
            return None
    else:
        active_event = await get_pending_active_event(owner_discord_id)
        if active_event is None:
            return None

    event = active_event.event
    context = EventContext.from_dict(active_event.context)

    options = []
    if event.requires_response:
        for option in sorted(event.options, key=lambda o: o.option_order):
            options.append(
                {
                    "id": option.id,
                    "label": option.label,
                    "description": option.description,
                    "min_money": option.min_money,
                    "min_bloodskulls": option.min_bloodskulls,
                }
            )

    return TriggeredEvent(
        active_event_id=active_event.id,
        event_id=event.id,
        name=event.name,
        category=event.category,
        description=event.description,
        flavor_text=event.flavor_text,
        severity=event.severity,
        requires_response=event.requires_response,
        response_timeout=event.response_timeout,
        expires_at=active_event.expires_at,
        context=context,
        options=options,
    )


async def list_all_events() -> list[dict[str, Any]]:
    """
    List all available events.

    Returns
    -------
    list[dict]
        A list of event information dictionaries.
    """

    events = await db_list_all_events()
    return [
        {
            "id": event.id,
            "name": event.name,
            "category": event.category,
            "description": event.description,
            "severity": event.severity,
            "rarity": event.rarity,
            "requires_response": event.requires_response,
        }
        for event in events
    ]


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
        List of (owner_discord_id, event_id, result) for processed events.
    """

    if rng is None:
        rng = random.Random()

    expired_events = await list_expired_active_events()
    results = []

    for active_event in expired_events:
        context = EventContext.from_dict(active_event.context)

        event = active_event.event
        result = await _execute_event_actions(active_event.owner_discord_id, event.actions, context, rng)
        result.message = f"Event '{event.name}' expired without response. {result.message}"

        await respond_to_active_event(active_event.id, None, result.to_dict())
        await archive_active_event(active_event.id, timed_out=True)

        results.append((active_event.owner_discord_id, event.id, result))
        logger.info(f"Processed expired event {active_event.id} for owner " f"{active_event.owner_discord_id}")

    return results


async def respond_to_event(
    owner_discord_id: int, active_event_id: int, option_id: int, rng: Optional[random.Random] = None
) -> tuple[bool, str, Optional[EventResult]]:
    """
    Process a player's response to an event.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner responding.

    active_event_id: int
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

    active_event = await get_active_event_by_id(active_event_id)
    if active_event is None:
        return False, "Event not found.", None

    if active_event.owner_discord_id != owner_discord_id:
        return False, "This event is not for you.", None

    if active_event.responded_at is not None:
        return False, "You have already responded to this event.", None

    if active_event.expires_at and datetime.now(timezone.utc) > active_event.expires_at:
        await archive_active_event(active_event_id, timed_out=True)
        return False, "This event has expired.", None

    option = await get_event_option_by_id(option_id)
    if option is None:
        return False, "Invalid option.", None

    if option.event_id != active_event.event_id:
        return False, "This option is not valid for this event.", None

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", None

    if owner.dollars < option.min_money:
        return False, f"You need at least ${option.min_money} to select this option.", None

    if owner.bloodskulls < option.min_bloodskulls:
        return False, f"You need at least {option.min_bloodskulls} bloodskulls to select this option.", None

    context = EventContext.from_dict(active_event.context)
    result = await _execute_event_actions(owner_discord_id, option.actions, context, rng)

    await respond_to_active_event(active_event_id, option_id, result.to_dict())
    await archive_active_event(active_event_id)

    logger.info(f"Owner {owner_discord_id} responded to event {active_event_id} with option {option_id}.")

    return True, f"You selected: {option.label}.", result


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
        Dictionary mapping owner Discord IDs to triggered events.
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

    logger.info(f"Hourly event check complete. {len(triggered_events)} owners received events.")

    return triggered_events


async def _create_event_context(owner_discord_id: int, event: Event, rng: random.Random) -> EventContext:
    """
    Create context for an event based on its requirements.

    This pre-selects random targets for actions that need them.
    Dynamic runtime entities are never referenced by literal IDs in static events.
    Instead, event actions use string selectors for dynamic targets:
    - `pooch` with `pooch_id` of `selected` or `random`
    - `kennel` with `kennel_id` of `selected` or `random`
    - `all_pooches` targets all of the owner's living pooches
    - `all_kennels` targets all of the owner's kennels
    """

    context = EventContext(owner_discord_id=owner_discord_id)

    kennels = await list_kennels_for_owner(owner_discord_id)
    context.affected_kennel_ids = [kennel.id for kennel in kennels]

    all_pooch_ids = []
    for kennel in kennels:
        pooches = await list_pooches_for_kennel(kennel.id)
        all_pooch_ids.extend([pooch.id for pooch in pooches if pooch.alive])
    context.affected_pooch_ids = all_pooch_ids

    def _uses_random_selector(action: EventAction, field_name: str) -> bool:
        if action.target_type not in {"pooch", "kennel"}:
            return False
        selector = action.parameters.get(field_name)
        return isinstance(selector, str) and selector.strip().lower() == "random"

    needs_random_pooch = any(_uses_random_selector(action, "pooch_id") for action in event.actions)
    needs_random_kennel = any(_uses_random_selector(action, "kennel_id") for action in event.actions)

    for option in event.options:
        for action in option.actions:
            needs_random_pooch = needs_random_pooch or _uses_random_selector(action, "pooch_id")
            needs_random_kennel = needs_random_kennel or _uses_random_selector(action, "kennel_id")

    if needs_random_pooch and all_pooch_ids:
        context.selected_pooch_id = rng.choice(all_pooch_ids)

    if needs_random_kennel and kennels:
        context.selected_kennel_id = rng.choice([kennel.id for kennel in kennels])

    return context


async def _execute_single_action(
    owner_discord_id: int, action: EventAction, context: EventContext, rng: random.Random
) -> EventResult:
    """
    Execute a single event action.

    Target type semantics:
    - `owner`: Target the owner directly (for money, bloodskulls, etc.)
    - `pooch`: Target the contextual pooch specified by the `pooch_id` selector.
               Supported selectors are `selected` and `random`.
    - `all_pooches`: Target all living pooches owned by the player.
    - `kennel`: Target the contextual kennel specified by the `kennel_id` selector.
                Supported selectors are `selected` and `random`.
    - `all_kennels`: Target all kennels owned by the player.
    """

    def _get_amount_from_params(params: dict[str, Any], rng: random.Random) -> int:
        """
        Get an amount from action parameters, supporting both fixed and random ranges.
        """

        if "min_amount" in params and "max_amount" in params:
            return rng.randint(int(params["min_amount"]), int(params["max_amount"]))
        return int(params.get("amount", 0))

    def _get_target_pooch_ids(target_type: str, context: EventContext, params: dict[str, Any]) -> list[int]:
        """
        Get the target pooch ID(s) based on target type.

        Target types:
        - `pooch`: Returns the contextual pooch selected by the `pooch_id` selector
        - `all_pooches`: Returns all living pooches owned by the player
        """

        if target_type == "pooch":
            selector = params.get("pooch_id")
            if isinstance(selector, str) and selector.strip().lower() in {"selected", "random"}:
                return [context.selected_pooch_id] if context.selected_pooch_id else []
            return []

        elif target_type == "all_pooches":
            return context.affected_pooch_ids

        return []

    def _get_target_kennel_ids(target_type: str, context: EventContext, params: dict[str, Any]) -> list[int]:
        """
        Get the target kennel ID(s) based on target type.

        Target types:
        - `kennel`: Returns the contextual kennel selected by the `kennel_id` selector
        - `all_kennels`: Returns all kennels owned by the player
        """

        if target_type == "kennel":
            selector = params.get("kennel_id")
            if isinstance(selector, str) and selector.strip().lower() in {"selected", "random"}:
                return [context.selected_kennel_id] if context.selected_kennel_id else []
            return []

        elif target_type == "all_kennels":
            return context.affected_kennel_ids

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
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            amount = _get_amount_from_params(params, rng)
            for pooch_id in pooch_ids:
                pooch = await modify_pooch_base_health(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("health_changes", {})[pooch_id] = amount

        elif action_type == "modify_pooch_age":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            amount = _get_amount_from_params(params, rng)
            for pooch_id in pooch_ids:
                pooch = await modify_pooch_age(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("age_changes", {})[pooch_id] = amount

        elif action_type == "kill_pooch":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            for pooch_id in pooch_ids:
                pooch = await set_pooch_dead(pooch_id)
                if pooch:
                    result.pooches_killed.append(pooch_id)
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = "A pooch has died!" if count == 1 else f"{count} pooches have died!"

        elif action_type == "add_mutation":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            mutation_id = params.get("mutation_id")
            for pooch_id in pooch_ids:
                if mutation_id:
                    mutation = await add_mutation_to_pooch(pooch_id, mutation_id)
                else:
                    mutation = await add_mutation_to_pooch(pooch_id, rng=rng)
                if mutation:
                    result.mutations_added.append((pooch_id, mutation.mutation_id))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "remove_mutation":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
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
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            breed_id = params.get("breed_id")
            weight = params.get("weight", 0.5)
            for pooch_id in pooch_ids:
                if breed_id:
                    await add_breed_to_pooch(pooch_id, breed_id, weight=weight)
                else:
                    await add_breed_to_pooch(pooch_id, rng=rng, weight=weight)
                result.pooches_affected.append(pooch_id)

        elif action_type == "transfer_pooch":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            new_owner_id = params.get("new_owner_discord_id")
            vendor_id = params.get("vendor_id")
            for pooch_id in pooch_ids:
                if new_owner_id:
                    await transfer_pooch_to_owner(pooch_id, new_owner_id)
                elif vendor_id:
                    await transfer_pooch_to_vendor(pooch_id, vendor_id)
                result.pooches_affected.append(pooch_id)

        elif action_type == "set_breeding_cooldown":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            cooldown = params.get("cooldown", 0)
            for pooch_id in pooch_ids:
                await set_pooch_breeding_cooldown(pooch_id, cooldown)
                result.pooches_affected.append(pooch_id)

        elif action_type == "rename_pooch":
            pooch_ids = _get_target_pooch_ids(target_type, context, params)
            new_name = params.get("name")
            if new_name:
                for pooch_id in pooch_ids:
                    await rename_pooch(pooch_id, new_name)
                    result.pooches_affected.append(pooch_id)

        elif action_type == "modify_kennel_capacity":
            kennel_ids = _get_target_kennel_ids(target_type, context, params)
            amount = _get_amount_from_params(params, rng)
            for kennel_id in kennel_ids:
                kennel = await modify_kennel_pooch_limit(kennel_id, amount)
                if kennel:
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
                if pooch.id not in context.affected_pooch_ids:
                    context.affected_pooch_ids.append(pooch.id)
                result.pooches_created.append(pooch.id)
                result.pooches_affected.append(pooch.id)
                result.message = "A new pooch has appeared!"

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

    active_event = await create_active_event(
        event_id=event.id,
        owner_discord_id=owner_discord_id,
        context=context.to_dict(),
        expires_at=expires_at,
    )

    if active_event is None:
        logger.error(f"Failed to create active event for owner {owner_discord_id}")
        return None

    logger.info(f"Triggered event '{event.name}' for owner {owner_discord_id}")

    result = None

    if not event.requires_response:
        result = await _execute_event_actions(owner_discord_id, event.actions, context, rng)
        await update_active_event_result(active_event.id, result.to_dict())
        await archive_active_event(active_event.id)

    options = []
    if event.requires_response:
        for option in sorted(event.options, key=lambda o: o.option_order):
            options.append(
                {
                    "id": option.id,
                    "label": option.label,
                    "description": option.description,
                    "min_money": option.min_money,
                    "min_bloodskulls": option.min_bloodskulls,
                }
            )

    triggered = TriggeredEvent(
        active_event_id=active_event.id,
        event_id=event.id,
        name=event.name,
        category=event.category,
        description=event.description,
        flavor_text=event.flavor_text,
        severity=event.severity,
        requires_response=event.requires_response,
        response_timeout=event.response_timeout,
        expires_at=expires_at,
        context=context,
        options=options,
        result=result,
    )

    return triggered


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
    active_events = await list_active_events_for_owner(owner_discord_id, pending_only=True)
    if len(active_events) >= EVENT_MAX_ACTIVE_PER_OWNER:
        logger.debug(f"Owner {owner_discord_id} has max active events, skipping trigger...")
        return None

    selected_event = await get_random_eligible_event_for_owner(owner_discord_id, rng=rng)

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

    event = await db_get_event_by_id(event_id)
    if event is None:
        logger.warning(f"Event {event_id} not found")
        return None

    return await _create_and_execute_event(owner_discord_id, event, rng)
