from __future__ import annotations

import logging
import random
from typing import Optional

from src.database import (
    archive_active_event,
    check_owner_event_filter_for_owner,
    get_active_owner_event_by_id,
    get_current_season,
    get_owner_by_discord_id,
)
from src.database import get_owner_event_by_id as db_get_owner_event_by_id
from src.database import get_owner_event_by_name as db_get_owner_event_by_name
from src.database import (
    get_owner_event_option_by_id,
    get_pending_active_owner_event,
    get_random_eligible_owner_event_for_owner,
    list_active_owner_events_for_owner,
)
from src.database import list_all_owner_events as db_list_all_owner_events
from src.database import (
    list_expired_active_owner_events,
    list_owner_event_history_for_owner,
    list_owners,
    respond_to_active_owner_event,
)
from src.game.constants import EVENT_HOURLY_TRIGGER_CHANCE, EVENT_MAX_ACTIVE_PER_OWNER
from src.game.models import (
    OwnerEvent,
    OwnerEventContext,
    OwnerEventHistory,
    OwnerEventResult,
    TriggeredOwnerEvent,
    to_owner_event,
    to_owner_event_history,
    to_triggered_owner_event,
)

from .coordinator import create_and_execute_event, execute_event_actions
from .outcome import choose_option_outcome

logger = logging.getLogger(__name__)


async def get_active_events_for_owner(owner_discord_id: int, pending_only: bool = True) -> list[TriggeredOwnerEvent]:
    """
    Get active events for owner.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    pending_only: Any
        The `pending_only` value.

    Returns
    -------
    Any
        The result of calling `get_active_events_for_owner`.
    """

    active_events = await list_active_owner_events_for_owner(owner_discord_id, pending_only=pending_only)
    return [await to_triggered_owner_event(active_event) for active_event in active_events]


async def get_event_history(owner_discord_id: int, limit: int = 50) -> list[OwnerEventHistory]:
    """
    Get event history.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    limit: Any
        The `limit` value.

    Returns
    -------
    Any
        The result of calling `get_event_history`.
    """

    history = await list_owner_event_history_for_owner(owner_discord_id, limit)
    return [await to_owner_event_history(record) for record in history]


async def get_pending_event(
    owner_discord_id: int, active_owner_event_id: Optional[int] = None
) -> Optional[TriggeredOwnerEvent]:
    """
    Get pending event.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    active_owner_event_id: Any
        The `active_owner_event_id` value.

    Returns
    -------
    Any
        The result of calling `get_pending_event`.
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

    return await to_triggered_owner_event(active_event)


async def list_all_owner_events() -> list[OwnerEvent]:
    """
    List all owner events.

    Returns
    -------
    Any
        The result of calling `list_all_owner_events`.
    """

    events = await db_list_all_owner_events()
    return [await to_owner_event(event) for event in events]


async def process_expired_events(rng: Optional[random.Random] = None) -> list[tuple[int, int, OwnerEventResult]]:
    """
    Process expired events.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `process_expired_events`.
    """

    if rng is None:
        rng = random.Random()

    expired_events = await list_expired_active_owner_events()
    results = []

    for active_event in expired_events:
        gone_pooch = await get_unavailable_featured_pooch_name(active_event, active_event.owner_discord_id)
        if gone_pooch is not None:
            await cancel_event_for_unavailable_pooch(active_event, gone_pooch)
            continue

        context = OwnerEventContext.from_dict(active_event.context)
        event = active_event.event

        result = (
            OwnerEventResult.from_dict(active_event.result_summary)
            if active_event.result_summary
            else OwnerEventResult()
        )

        default_option = next((opt for opt in event.options if opt.is_default), None)
        responded_option_id = None

        if default_option is not None:
            responded_option_id = default_option.id
            option_result = await execute_event_actions(
                active_event.owner_discord_id, default_option.actions, context, rng
            )
            result.merge(option_result)

            selected_outcome = await choose_option_outcome(default_option, context, rng)
            if selected_outcome is not None:
                outcome_result = await execute_event_actions(
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
                result.message = (
                    outcome_message or f"OwnerEvent '{event.name}' expired. {default_option.label} was applied."
                )
            else:
                result.message = f"OwnerEvent '{event.name}' expired. {default_option.label} was applied."
        else:
            result.message = f"OwnerEvent '{event.name}' expired without response. {result.message}".strip()

        await respond_to_active_owner_event(active_event.id, responded_option_id, result.to_dict())
        await archive_active_event(active_event.id, timed_out=True)

        results.append((active_event.owner_discord_id, event.id, result))
        logger.info(f"Processed expired event {active_event.id} for owner {active_event.owner_discord_id}")

    return results


async def get_unavailable_featured_pooch_name(active_event, owner_discord_id: int) -> Optional[str]:
    """
    Name the event's featured pooch if it can no longer be offered: it died, went to a vendor
    or belongs to another player now. Events with no featured pooch are always available.

    Parameters
    ----------
    active_event: EventOccurrence
        The active event to check.

    owner_discord_id: int
        The Discord ID of the owner the event belongs to.

    Returns
    -------
    str, optional
        The featured pooch's name if it's gone, otherwise None.
    """

    from src.database import get_pooch_by_id

    context = OwnerEventContext.from_dict(active_event.context)
    slot_name = context.extra_data.get("_featured_pooch_slot")
    if not isinstance(slot_name, str) or not slot_name:
        return None
    slot = context.extra_data.get(slot_name, {})
    pooch_ids = slot.get("pooch_ids", []) if isinstance(slot, dict) else []
    if not pooch_ids:
        return None

    pooch = await get_pooch_by_id(pooch_ids[0])
    if pooch is None:
        return "The pooch"
    owned_elsewhere = pooch.owner_discord_id is not None and pooch.owner_discord_id != owner_discord_id
    if not pooch.alive or pooch.vendor_id is not None or owned_elsewhere:
        return pooch.name
    return None


async def cancel_event_for_unavailable_pooch(active_event, pooch_name: str) -> str:
    """
    Close an event whose featured pooch is gone without applying any option.

    Parameters
    ----------
    active_event: EventOccurrence
        The active event to close.

    pooch_name: str
        The featured pooch's name, for the message.

    Returns
    -------
    str
        The message explaining why the event was called off.
    """

    message = f"**{pooch_name}** is no longer available, so **{active_event.event.name}** is off."
    result = OwnerEventResult()
    result.message = message
    await respond_to_active_owner_event(active_event.id, None, result.to_dict())
    await archive_active_event(active_event.id)
    return message


async def respond_to_event(
    owner_discord_id: int, active_owner_event_id: int, option_id: int, rng: Optional[random.Random] = None
) -> tuple[bool, str, Optional[OwnerEventResult]]:
    """
    Respond to event.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    active_owner_event_id: Any
        The `active_owner_event_id` value.

    option_id: Any
        The `option_id` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `respond_to_event`.
    """

    if rng is None:
        rng = random.Random()

    active_event = await get_active_owner_event_by_id(active_owner_event_id)
    if active_event is None:
        return False, "OwnerEvent not found.", None

    if active_event.owner_discord_id != owner_discord_id:
        return False, "This event is not for you.", None

    if active_event.responded_at is not None:
        return False, "You have already responded to this event.", None

    from datetime import datetime, timezone

    if active_event.expires_at and datetime.now(timezone.utc) > active_event.expires_at:
        await archive_active_event(active_owner_event_id, timed_out=True)
        return False, "This event has expired.", None

    gone_pooch = await get_unavailable_featured_pooch_name(active_event, owner_discord_id)
    if gone_pooch is not None:
        return False, await cancel_event_for_unavailable_pooch(active_event, gone_pooch), None

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

    context = OwnerEventContext.from_dict(active_event.context)
    result = (
        OwnerEventResult.from_dict(active_event.result_summary) if active_event.result_summary else OwnerEventResult()
    )
    option_result = await execute_event_actions(owner_discord_id, option.actions, context, rng)
    result.merge(option_result)

    selected_outcome = await choose_option_outcome(option, context, rng)
    outcome_message = None
    if selected_outcome is not None:
        outcome_result = await execute_event_actions(owner_discord_id, selected_outcome.actions, context, rng)
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


async def run_hourly_event_check(rng_seed: Optional[int] = None) -> dict[int, list[TriggeredOwnerEvent]]:
    """
    Run hourly event check.

    Parameters
    ----------
    rng_seed: Any
        The `rng_seed` value.

    Returns
    -------
    Any
        The result of calling `run_hourly_event_check`.
    """

    if rng_seed is not None:
        rng = random.Random(rng_seed)
    else:
        rng = random.Random()

    await process_expired_events(rng)

    owners = await list_owners()
    triggered_events: dict[int, list[TriggeredOwnerEvent]] = {}

    for owner in owners:
        # Call off pending offers whose pooch died or changed hands this hour, so they stop showing.
        for active_event in await list_active_owner_events_for_owner(owner.discord_id, pending_only=True):
            gone_pooch = await get_unavailable_featured_pooch_name(active_event, owner.discord_id)
            if gone_pooch is not None:
                await cancel_event_for_unavailable_pooch(active_event, gone_pooch)

        if rng.random() > EVENT_HOURLY_TRIGGER_CHANCE:
            continue

        event = await trigger_random_event(owner.discord_id, rng)
        if event is not None:
            if owner.discord_id not in triggered_events:
                triggered_events[owner.discord_id] = []
            triggered_events[owner.discord_id].append(event)

    logger.info(f"Hourly event check complete. {len(triggered_events)} owners received owner_events.")
    return triggered_events


async def trigger_random_event(
    owner_discord_id: int, rng: Optional[random.Random] = None
) -> Optional[TriggeredOwnerEvent]:
    """
    Trigger random event.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `trigger_random_event`.
    """

    if rng is None:
        rng = random.Random()

    active_events = await list_active_owner_events_for_owner(owner_discord_id, pending_only=True)
    if len(active_events) >= EVENT_MAX_ACTIVE_PER_OWNER:
        logger.debug(f"Owner {owner_discord_id} has max active events, skipping trigger...")
        return None

    selected_event = await get_random_eligible_owner_event_for_owner(
        owner_discord_id, rng=rng, season=await get_current_season()
    )

    if selected_event is None:
        logger.debug(f"No eligible events for owner {owner_discord_id}.")
        return None

    return await create_and_execute_event(owner_discord_id, selected_event, rng)


async def trigger_specific_event(
    owner_discord_id: int,
    event_id: int,
    rng: Optional[random.Random] = None,
    inherited_slots: Optional[dict] = None,
) -> Optional[TriggeredOwnerEvent]:
    """
    Trigger specific event.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    event_id: Any
        The `event_id` value.

    rng: Any
        The `rng` value.

    inherited_slots: Any
        The `inherited_slots` value.

    Returns
    -------
    Any
        The result of calling `trigger_specific_event`.
    """

    if rng is None:
        rng = random.Random()

    event = await db_get_owner_event_by_id(event_id)
    if event is None:
        logger.warning(f"OwnerEvent {event_id} not found")
        return None

    return await create_and_execute_event(owner_discord_id, event, rng, inherited_slots=inherited_slots)


async def trigger_event_by_name(
    owner_discord_id: int, event_name: str, rng: Optional[random.Random] = None
) -> Optional[TriggeredOwnerEvent]:
    """
    Trigger event by name.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    event_name: Any
        The `event_name` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `trigger_event_by_name`.
    """

    event = await db_get_owner_event_by_name(event_name)
    if event is None:
        logger.warning(f"OwnerEvent '{event_name}' not found")
        return None

    return await trigger_specific_event(owner_discord_id, event.id, rng)
