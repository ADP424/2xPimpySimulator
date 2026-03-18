import logging
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from src.database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    add_pooch_breeds,
    add_pooch_to_kennel,
    add_pooch_to_strays,
    add_pooch_to_vendor_stock,
    archive_active_event,
    bury_pooch,
    check_owner_event_filter_for_owner,
    create_active_owner_event,
    create_pooch,
    damn_pooch,
    delete_pooch,
    get_active_owner_event_by_id,
    get_kennel_by_id,
    get_mutation_by_name,
    get_owner_by_discord_id,
)
from src.database import get_owner_event_by_id as db_get_owner_event_by_id
from src.database import get_owner_event_by_name as db_get_owner_event_by_name
from src.database import (
    get_owner_event_option_by_id,
    get_pending_active_owner_event,
    get_pooch_aggressiveness,
    get_pooch_base_health,
    get_pooch_by_id,
    get_pooch_cuteness,
    get_pooch_dexterity,
    get_pooch_fertility,
    get_pooch_fluffiness,
    get_pooch_intelligence,
    get_pooch_kennel,
    get_pooch_strength,
    get_random_eligible_owner_event_for_owner,
    get_random_matching_kennel_id,
    get_random_matching_pooch_id,
    give_bloodskulls_to_owner,
    give_bones_to_owner,
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
    list_pooch_breeds,
    list_pooch_mutations,
    list_pooches_for_kennel,
    list_servers_for_owner,
    list_strays_for_server,
    list_vendor_pooch_stock,
    list_vendors,
    modify_kennel_pooch_limit,
    modify_pooch_age,
    modify_pooch_aggressiveness,
    modify_pooch_base_health,
    modify_pooch_breeding_cooldown,
    modify_pooch_cuteness,
    modify_pooch_dexterity,
    modify_pooch_fertility,
    modify_pooch_fluffiness,
    modify_pooch_intelligence,
    modify_pooch_strength,
    remove_breed_from_pooch,
    remove_mutation_from_pooch,
    remove_pooch_from_kennel,
    remove_pooch_from_strays,
    remove_pooch_from_vendor_stock,
    remove_random_breed_from_pooch,
    remove_random_mutation_from_pooch,
    rename_pooch,
    reset_pooch_breeding_cooldown,
    respond_to_active_owner_event,
    revive_pooch,
    set_kennel_pooch_limit,
    set_owner_bloodskulls,
    set_owner_dollars,
    set_pooch_age,
    set_pooch_aggressiveness,
    set_pooch_base_health,
    set_pooch_breeding_cooldown,
    set_pooch_cuteness,
    set_pooch_dead,
    set_pooch_dexterity,
    set_pooch_fertility,
    set_pooch_fluffiness,
    set_pooch_intelligence,
    set_pooch_strength,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
    update_active_event_context,
    update_active_event_result,
)

from .breeding import breed_pooches
from .constants import (
    EVENT_HOURLY_TRIGGER_CHANCE,
    EVENT_MAX_ACTIVE_PER_OWNER,
    NUM_BREEDS_PER_SUMMON_POOCH_RANGE,
    POOCH_BREEDING_COOLDOWN,
    POOCH_STAT_RANGE,
    POOCH_STATS,
)
from .manage_hell import get_pooch_bloodskull_value
from .manage_vendors import get_pooch_buy_price, get_pooch_sell_price
from .models import (
    OwnerEvent,
    OwnerEventContext,
    OwnerEventHistory,
    OwnerEventResult,
    StrayEventContext,
    TriggeredOwnerEvent,
    to_owner_event,
    to_owner_event_history,
    to_triggered_owner_event,
)

if TYPE_CHECKING:
    from src.database.models import Event as EventDB
    from src.database.models import EventAction, EventOption, EventOutcome


logger = logging.getLogger(__name__)


async def get_active_events_for_owner(owner_discord_id: int, pending_only: bool = True) -> list[TriggeredOwnerEvent]:
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
    list[TriggeredOwnerEvent]
        List of triggered events for the owner.
    """

    active_events = await list_active_owner_events_for_owner(owner_discord_id, pending_only=pending_only)
    return [await to_triggered_owner_event(active_event) for active_event in active_events]


async def get_event_history(owner_discord_id: int, limit: int = 50) -> list[OwnerEventHistory]:
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
    list[OwnerEventHistory]
        List of typed event history records.
    """

    history = await list_owner_event_history_for_owner(owner_discord_id, limit)
    return [await to_owner_event_history(record) for record in history]


async def get_pending_event(
    owner_discord_id: int, active_owner_event_id: Optional[int] = None
) -> Optional[TriggeredOwnerEvent]:
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
    TriggeredOwnerEvent, optional
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

    return await to_triggered_owner_event(active_event)


async def list_all_owner_events() -> list[OwnerEvent]:
    """
    List all available owner_events.

    Returns
    -------
    list[OwnerEvent]
        A list of typed event information objects.
    """

    events = await db_list_all_owner_events()
    return [await to_owner_event(event) for event in events]


async def process_expired_events(rng: Optional[random.Random] = None) -> list[tuple[int, int, OwnerEventResult]]:
    """
    Process all expired events that weren't responded to.

    Parameters
    ----------
    rng: Random, optional
        Random number generator for reproducibility.

    Returns
    -------
    list[tuple[int, int, OwnerEventResult]]
        List of (owner_discord_id, event_id, result) for processed owner_events.
    """

    if rng is None:
        rng = random.Random()

    expired_events = await list_expired_active_owner_events()
    results = []

    for active_event in expired_events:
        context = OwnerEventContext.from_dict(active_event.context)
        event = active_event.event

        # Start with any result already recorded from event-level actions at trigger time
        result = (
            OwnerEventResult.from_dict(active_event.result_summary)
            if active_event.result_summary
            else OwnerEventResult()
        )

        default_option = next((opt for opt in event.options if opt.is_default), None)
        responded_option_id = None

        if default_option is not None:
            responded_option_id = default_option.id
            option_result = await _execute_event_actions(
                active_event.owner_discord_id, default_option.actions, context, rng
            )
            result.merge(option_result)

            selected_outcome = await _choose_option_outcome(default_option, context, rng)
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


_SIZE_SCORES: dict[str, float] = {
    "tiny": 4.0,
    "small": 7.0,
    "average": 10.0,
    "large": 13.0,
    "massive": 16.0,
}

_STAT_GETTERS = {
    "strength": get_pooch_strength,
    "cuteness": get_pooch_cuteness,
    "fluffiness": get_pooch_fluffiness,
    "intelligence": get_pooch_intelligence,
    "dexterity": get_pooch_dexterity,
    "fertility": get_pooch_fertility,
    "aggressiveness": get_pooch_aggressiveness,
    "base_health": get_pooch_base_health,
}


def _resolve_single_stat_pooch_id_owner(
    selector: str,
    context: "OwnerEventContext",
    rng: random.Random,
) -> Optional[int]:
    """Resolve a single pooch ID for a stat_weights entry selector (owner event context)."""
    if selector == "random":
        return rng.choice(context.affected_pooch_ids) if context.affected_pooch_ids else None
    slot = context.extra_data.get(selector)
    if isinstance(slot, dict):
        ids = slot.get("pooch_ids", [])
        return ids[0] if ids else None
    return None


async def _get_effective_pooch_stat_owner(stat: str, pooch_id: int) -> Optional[float]:
    """Return the effective value of a named stat for a pooch."""
    if stat == "size":
        breed_pairs = await list_pooch_breeds(pooch_id)
        if not breed_pairs:
            return 10.0
        total_w = sum(w for _, w in breed_pairs)
        if total_w <= 0:
            return 10.0
        return sum(_SIZE_SCORES.get(breed.size, 10.0) * (w / total_w) for breed, w in breed_pairs)
    getter = _STAT_GETTERS.get(stat)
    if getter is None:
        return None
    result = await getter(pooch_id)
    return float(result) if result is not None else None


async def _compute_outcome_stat_multiplier_owner(
    stat_weights: list,
    context: "OwnerEventContext",
    rng: random.Random,
) -> float:
    """Compute the combined stat multiplier for a weighted owner event outcome."""
    multiplier = 1.0
    for entry in stat_weights:
        if not isinstance(entry, dict):
            continue
        stat = str(entry.get("stat", "")).strip().lower()
        selector = str(entry.get("pooch", "random")).strip().lower()
        scale = float(entry.get("scale", 0.0))
        pivot = float(entry.get("pivot", 10.0))
        direction = float(entry.get("direction", 1.0))

        pooch_id = _resolve_single_stat_pooch_id_owner(selector, context, rng)
        if pooch_id is None:
            continue

        effective = await _get_effective_pooch_stat_owner(stat, pooch_id)
        if effective is None:
            logger.warning(f"stat_weights: unknown stat '{stat}'; skipping entry")
            continue

        entry_mult = 1.0 + (effective - pivot) * scale * direction
        multiplier *= max(0.0, entry_mult)
    return multiplier


async def _choose_option_outcome(
    option: "EventOption", context: "OwnerEventContext", rng: random.Random
) -> "Optional[EventOutcome]":
    """Pick one outcome using weighted random selection with optional stat-based weighting.

    Outcomes are partitioned into three groups:
    - Fixed: explicit ``chance`` with no ``stat_weights`` — reserved probability, unchanged.
    - Weighted: have ``stat_weights`` (optionally also a base ``chance``) — compete for the
      remaining probability share after fixed outcomes are subtracted.
    - Implicit: no ``chance`` and no ``stat_weights`` — treated as weight-1 entries in the
      weighted pool.
    """
    if not option.outcomes:
        return None

    fixed = [o for o in option.outcomes if o.chance is not None and not o.stat_weights]
    dynamic = [o for o in option.outcomes if o.stat_weights or o.chance is None]

    if not dynamic:
        # All outcomes are fixed — standard weighted roll
        roll = rng.random()
        cumulative = 0.0
        for o in fixed:
            cumulative += float(o.chance)
            if roll < cumulative:
                return o
        return fixed[-1]

    fixed_total = sum(float(o.chance) for o in fixed)
    remaining = max(0.0, 1.0 - fixed_total)

    raw_scores: list[float] = []
    for o in dynamic:
        if o.stat_weights:
            base = float(o.chance) if o.chance is not None else 1.0
            multiplier = await _compute_outcome_stat_multiplier_owner(o.stat_weights, context, rng)
            raw_scores.append(max(0.0, base * multiplier))
        else:
            raw_scores.append(1.0)

    raw_sum = sum(raw_scores)
    if raw_sum <= 0:
        return rng.choice(option.outcomes)

    entries: list[tuple[EventOutcome, float]] = []
    for o, raw in zip(dynamic, raw_scores):
        entries.append((o, (raw / raw_sum) * remaining))
    for o in fixed:
        entries.append((o, float(o.chance)))

    roll = rng.random()
    cumulative = 0.0
    for outcome, weight in entries:
        cumulative += weight
        if roll < cumulative:
            return outcome
    return entries[-1][0]


async def respond_to_event(
    owner_discord_id: int, active_owner_event_id: int, option_id: int, rng: Optional[random.Random] = None
) -> tuple[bool, str, Optional[OwnerEventResult]]:
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
    tuple[bool, str, OwnerEventResult | None]
        Success status, message, and the result of the response.
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

    context = OwnerEventContext.from_dict(active_event.context)
    # Merge with any result already recorded from event-level actions at trigger time
    result = (
        OwnerEventResult.from_dict(active_event.result_summary) if active_event.result_summary else OwnerEventResult()
    )
    option_result = await _execute_event_actions(owner_discord_id, option.actions, context, rng)
    result.merge(option_result)

    selected_outcome = await _choose_option_outcome(option, context, rng)
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


async def run_hourly_event_check(rng_seed: Optional[int] = None) -> dict[int, list[TriggeredOwnerEvent]]:
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
    dict[int, list[TriggeredOwnerEvent]]
        Dictionary mapping owner Discord IDs to triggered owner_events.
    """

    if rng_seed is not None:
        rng = random.Random(rng_seed)
    else:
        rng = random.Random()

    await process_expired_events(rng)

    owners = await list_owners()

    triggered_events: dict[int, list[TriggeredOwnerEvent]] = {}

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


async def _create_event_context(owner_discord_id: int, event: EventDB, rng: random.Random) -> OwnerEventContext:
    """
    Create context for an event based on its requirements.

    This pre-selects contextual targets for actions that use the `selected` selector.
    Random targets are resolved when the action executes so they can respect action filters.
    """

    context = OwnerEventContext(owner_discord_id=owner_discord_id)

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
    For "town", releases the pooch as a stray on a random server the owner belongs to.
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
        destination = "town"

    if destination == "town":
        servers = await list_servers_for_owner(owner_discord_id)
        if servers:
            server = random.choice(servers)
            await add_pooch_to_strays(pooch_id, server.discord_id)
        return "town", None

    elif destination == "graveyard":
        await bury_pooch(owner_discord_id, pooch_id)
        return "graveyard", None

    elif destination == "hell":
        await damn_pooch(pooch_id)
        return "hell", None

    else:  # unknown
        return "town", None


async def _execute_single_action(
    owner_discord_id: int, action: EventAction, context: OwnerEventContext, rng: random.Random
) -> OwnerEventResult:
    """
    Execute a single event action.
    """

    def _get_amount_from_parameters(parameters: dict[str, Any], rng: random.Random) -> int:
        if "min_amount" in parameters and "max_amount" in parameters:
            exclude = parameters.get("exclude_amount", [])
            exclude_set = set(exclude) if isinstance(exclude, list) else set()
            lo, hi = parameters["min_amount"], parameters["max_amount"]
            candidates = [v for v in range(lo, hi + 1) if v not in exclude_set]
            return rng.choice(candidates) if candidates else lo
        return parameters.get("amount", 0)

    def _resolve_amount(parameters: dict[str, Any], rng: random.Random) -> tuple[int | None, bool]:
        """Return (pre_rolled_amount_or_None, roll_once). If roll_once, the amount is already rolled."""
        roll_once = bool(parameters.get("roll_once", False))
        if roll_once:
            return _get_amount_from_parameters(parameters, rng), True
        return None, False

    def _get_mode(parameters: dict[str, Any]) -> str:
        """Return 'set' or 'modify' (default)."""
        raw = parameters.get("mode", "modify")
        return "set" if isinstance(raw, str) and raw.strip().lower() == "set" else "modify"

    async def _get_target_pooch_ids(target_type: str, selector: str, parameters: dict[str, Any]) -> list[int]:
        action_filter = parameters.get("filter", {})
        filter_spec = action_filter if isinstance(action_filter, dict) else {}
        count_param = parameters.get("count")
        count = int(count_param) if isinstance(count_param, int) and count_param > 0 else None

        # _exclude_ids: internal list of pooch IDs to exclude from random resolution (used by exclude_claimed preflight)
        exclude_ids_raw = parameters.get("_exclude_ids", [])
        exclude_ids: set[int] = set(exclude_ids_raw) if isinstance(exclude_ids_raw, list) else set()

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
            if exclude_ids:
                pooch_ids = [pid for pid in pooch_ids if pid not in exclude_ids]
        elif target_type == "pooch":
            if selector == "selected":
                pooch_ids = [context.selected_pooch_id] if context.selected_pooch_id else []
            elif selector == "random":
                all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
                if exclude_ids:
                    all_ids = [pid for pid in all_ids if pid not in exclude_ids]
                if count is not None:
                    pooch_ids = rng.sample(all_ids, min(count, len(all_ids))) if all_ids else []
                else:
                    pooch_ids = [rng.choice(all_ids)] if all_ids else []
            elif selector == "all":
                all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
                pooch_ids = [pid for pid in all_ids if pid not in exclude_ids] if exclude_ids else all_ids
            elif selector == "random_exclude":
                all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
                if exclude_ids:
                    all_ids = [pid for pid in all_ids if pid not in exclude_ids]
                if count is not None and count < len(all_ids):
                    excluded = set(rng.sample(all_ids, count))
                    pooch_ids = [pid for pid in all_ids if pid not in excluded]
                else:
                    pooch_ids = []
            elif selector == "all_exclude":
                # "all_exclude" with a filter: targets every pooch NOT matched by the filter
                all_owner_ids = await list_matching_pooch_ids(owner_discord_id, {})
                matched_ids = set(await list_matching_pooch_ids(owner_discord_id, filter_spec))
                pooch_ids = [pid for pid in all_owner_ids if pid not in matched_ids]
                if exclude_ids:
                    pooch_ids = [pid for pid in pooch_ids if pid not in exclude_ids]
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
            elif selector == "all_exclude":
                # targets every kennel NOT matched by the filter
                all_owner_kennel_ids = await list_matching_kennel_ids(owner_discord_id, {})
                matched_kennel_ids = set(await list_matching_kennel_ids(owner_discord_id, kennel_filter))
                kennel_ids = [kid for kid in all_owner_kennel_ids if kid not in matched_kennel_ids]
            else:
                kennel_ids = []

            # pooch_selector/pooch_count: control which pooches within the resolved kennels are targeted
            raw_pooch_selector = parameters.get("pooch_selector")
            pooch_selector = str(raw_pooch_selector).strip().lower() if isinstance(raw_pooch_selector, str) else None
            pooch_count_raw = parameters.get("pooch_count")
            pooch_count = int(pooch_count_raw) if isinstance(pooch_count_raw, int) and pooch_count_raw > 0 else None

            pooch_ids = []
            for kennel_id in kennel_ids:
                kennel_pooches = await list_matching_pooch_ids_in_kennel(owner_discord_id, kennel_id, pooch_filter)
                if pooch_selector == "random":
                    n = pooch_count if pooch_count is not None else 1
                    pooch_ids.extend(rng.sample(kennel_pooches, min(n, len(kennel_pooches))) if kennel_pooches else [])
                elif pooch_selector == "random_exclude":
                    n = pooch_count if pooch_count is not None else 1
                    if n < len(kennel_pooches):
                        excluded = set(rng.sample(kennel_pooches, n))
                        pooch_ids.extend(pid for pid in kennel_pooches if pid not in excluded)
                    # if count >= len, nothing survives the exclusion — pooch_ids stays empty for this kennel
                else:
                    pooch_ids.extend(kennel_pooches)

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
        elif selector == "all_exclude":
            all_owner_kennel_ids = await list_matching_kennel_ids(owner_discord_id, {})
            matched_kennel_ids = set(await list_matching_kennel_ids(owner_discord_id, filter_spec))
            kennel_ids = [kid for kid in all_owner_kennel_ids if kid not in matched_kennel_ids]
        else:
            kennel_ids = []

        # save_as: store resolved kennel IDs into a named slot
        save_as = parameters.get("save_as")
        if isinstance(save_as, str) and save_as:
            context.extra_data[save_as] = {"kennel_ids": kennel_ids}

        return kennel_ids

    result = OwnerEventResult()
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
            if _get_mode(parameters) == "set":
                await set_owner_dollars(owner_discord_id, amount)
            else:
                await give_money_to_owner(owner_discord_id, amount)
            result.money_changed = amount
            result.message = f"{amount:+d} dollars"

        elif action_type == "modify_bloodskulls":
            amount = _get_amount_from_parameters(parameters, rng)
            if _get_mode(parameters) == "set":
                await set_owner_bloodskulls(owner_discord_id, amount)
            else:
                await give_bloodskulls_to_owner(owner_discord_id, amount)
            result.bloodskulls_changed = amount
            result.message = f"{amount:+d} bloodskulls"

        elif action_type == "create_pooch":
            create_pooch_kwargs: dict[str, Any] = {
                "owner_discord_id": owner_discord_id,
                "rng": rng,
            }
            for _key in (
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
                "breeding_cooldown",
            ):
                if _key in parameters:
                    create_pooch_kwargs[_key] = parameters[_key]

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

                if target_type == "kennel":
                    kennel_ids = await _get_target_kennel_ids(target_type, selector, parameters)
                    kennel_id = kennel_ids[0] if kennel_ids else None
                    if kennel_id is not None:
                        kennel = await get_kennel_by_id(kennel_id)
                        pooches_in = await list_pooches_for_kennel(kennel_id)
                        if kennel is not None and len(pooches_in) < kennel.pooch_limit:
                            await add_pooch_to_kennel(kennel_id, pooch.id)
                            result.message = f"A new pooch has appeared and was placed in {kennel.name}!"
                        else:
                            result.message = "A new pooch has appeared but there was no space in the kennel!"
                    else:
                        result.message = "A new pooch has appeared!"
                else:
                    destination_str = parameters.get("destination", "kennel")
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
                        "strength": parameters.get("strength", source.strength),
                        "cuteness": parameters.get("cuteness", source.cuteness),
                        "fluffiness": parameters.get("fluffiness", source.fluffiness),
                        "intelligence": parameters.get("intelligence", source.intelligence),
                        "dexterity": parameters.get("dexterity", source.dexterity),
                        "fertility": parameters.get("fertility", source.fertility),
                        "aggressiveness": parameters.get("aggressiveness", source.aggressiveness),
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

                        destination_str = parameters.get("destination", "kennel")
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
            mode = _get_mode(parameters)
            for kennel_id in kennel_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                if mode == "set":
                    kennel = await set_kennel_pooch_limit(kennel_id, amount)
                else:
                    kennel = await modify_kennel_pooch_limit(kennel_id, amount)
                if kennel:
                    if kennel_id not in context.affected_kennel_ids:
                        context.affected_kennel_ids.append(kennel_id)
                    result.extra_data.setdefault("kennel_capacity_changes", {})[kennel_id] = amount

        # Pooch Actions
        elif action_type in ("modify_base_health", "modify_pooch_health"):
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            mode = _get_mode(parameters)
            for pooch_id in pooch_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                if mode == "set":
                    pooch = await set_pooch_base_health(pooch_id, amount)
                else:
                    pooch = await modify_pooch_base_health(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)
                    result.extra_data.setdefault("health_changes", {})[pooch_id] = amount

        elif action_type == "modify_pooch_age":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            mode = _get_mode(parameters)
            for pooch_id in pooch_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                if mode == "set":
                    pooch = await set_pooch_age(pooch_id, amount)
                else:
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

        elif action_type == "release_stray":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            servers = await list_servers_for_owner(owner_discord_id)
            if not servers:
                logger.warning("release_stray: owner has no servers; skipping")
            else:
                server = rng.choice(servers)
                for pooch_id in pooch_ids:
                    stray = await add_pooch_to_strays(pooch_id, server.discord_id)
                    if stray:
                        result.pooches_affected.append(pooch_id)

        elif action_type == "receive_stray":
            servers = await list_servers_for_owner(owner_discord_id)
            if not servers:
                logger.warning("receive_stray: owner has no servers; skipping")
            else:
                server = rng.choice(servers)
                use_saved = parameters.get("use_saved")
                if isinstance(use_saved, str) and use_saved:
                    saved = context.extra_data.get(use_saved, {})
                    saved_ids = list(saved.get("pooch_ids", [])) if isinstance(saved, dict) else []
                    pool_objs = [p for p in await list_strays_for_server(server.discord_id) if p.id in saved_ids]
                else:
                    candidates = await list_strays_for_server(server.discord_id)
                    count = int(parameters.get("count", 1))
                    pool_objs = rng.sample(candidates, min(count, len(candidates))) if candidates else []
                if not pool_objs:
                    logger.warning("receive_stray: no strays available on server %s; skipping", server.discord_id)
                else:
                    chosen = rng.choice(pool_objs)
                    await remove_pooch_from_strays(chosen.id)
                    await transfer_pooch_to_owner(chosen.id, owner_discord_id)

                    if target_type == "kennel":
                        kennel_ids = await _get_target_kennel_ids(target_type, selector, parameters)
                        recv_kennel_id = kennel_ids[0] if kennel_ids else None
                        if recv_kennel_id is not None:
                            kennel = await get_kennel_by_id(recv_kennel_id)
                            pooches_in = await list_pooches_for_kennel(recv_kennel_id)
                            if kennel is not None and len(pooches_in) < kennel.pooch_limit:
                                await add_pooch_to_kennel(recv_kennel_id, chosen.id)
                                dest_key, kennel_name = "kennel", kennel.name
                            else:
                                dest_key, kennel_name = "town", None
                        else:
                            dest_key, kennel_name = "town", None
                    else:
                        destination_str = str(parameters.get("destination", "kennel")).strip().lower()
                        dest_key, kennel_name = await _deliver_pooch(owner_discord_id, chosen.id, destination_str)

                    result.pooches_created.append(chosen.id)
                    result.extra_data.setdefault("created_pooches", []).append(
                        {
                            "pooch_id": chosen.id,
                            "pooch_name": chosen.name,
                            "sex": chosen.sex,
                            "age": chosen.age,
                            "kennel_name": kennel_name,
                        }
                    )

        elif action_type == "add_mutation":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            mutation_id = parameters.get("mutation_id")
            min_rarity = parameters.get("min_rarity")
            max_rarity = parameters.get("max_rarity")
            min_health_impact = parameters.get("min_health_impact")
            max_health_impact = parameters.get("max_health_impact")
            for pooch_id in pooch_ids:
                if mutation_id:
                    await add_mutation_to_pooch(pooch_id, mutation_id)
                else:
                    await add_mutation_to_pooch(
                        pooch_id,
                        rng=rng,
                        min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                        max_rarity=max_rarity if isinstance(max_rarity, str) else None,
                        min_health_impact=min_health_impact if isinstance(min_health_impact, str) else None,
                        max_health_impact=max_health_impact if isinstance(max_health_impact, str) else None,
                    )
                result.pooches_affected.append(pooch_id)

        elif action_type == "remove_mutation":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            mutation_id = parameters.get("mutation_id")
            min_rarity = parameters.get("min_rarity")
            max_rarity = parameters.get("max_rarity")
            min_health_impact = parameters.get("min_health_impact")
            max_health_impact = parameters.get("max_health_impact")
            for pooch_id in pooch_ids:
                if mutation_id:
                    removed = await remove_mutation_from_pooch(pooch_id, mutation_id)
                else:
                    removed = await remove_random_mutation_from_pooch(
                        pooch_id,
                        rng=rng,
                        min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                        max_rarity=max_rarity if isinstance(max_rarity, str) else None,
                        min_health_impact=min_health_impact if isinstance(min_health_impact, str) else None,
                        max_health_impact=max_health_impact if isinstance(max_health_impact, str) else None,
                    )
                if removed:
                    result.mutations_removed.append((pooch_id, removed.mutation_id))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "add_breed":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            breed_id = parameters.get("breed_id")
            weight = parameters.get("weight", 0.5)
            min_rarity = parameters.get("min_rarity")
            max_rarity = parameters.get("max_rarity")
            for pooch_id in pooch_ids:
                if breed_id:
                    await add_breed_to_pooch(pooch_id, breed_id, weight=weight)
                else:
                    await add_breed_to_pooch(
                        pooch_id,
                        rng=rng,
                        weight=weight,
                        min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                        max_rarity=max_rarity if isinstance(max_rarity, str) else None,
                    )
                result.pooches_affected.append(pooch_id)

        elif action_type == "remove_breed":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            breed_id = parameters.get("breed_id")
            min_rarity = parameters.get("min_rarity")
            max_rarity = parameters.get("max_rarity")
            for pooch_id in pooch_ids:
                if breed_id:
                    removed = await remove_breed_from_pooch(pooch_id, breed_id)
                else:
                    removed = await remove_random_breed_from_pooch(
                        pooch_id,
                        rng=rng,
                        min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                        max_rarity=max_rarity if isinstance(max_rarity, str) else None,
                    )
                if removed:
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

        elif action_type in ("modify_breeding_cooldown", "set_breeding_cooldown"):
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            cooldown = parameters.get("cooldown", 0)
            mode = _get_mode(parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            for pooch_id in pooch_ids:
                if isinstance(cooldown, str) and cooldown.strip().lower() == "base":
                    await reset_pooch_breeding_cooldown(pooch_id, base_cooldown=POOCH_BREEDING_COOLDOWN)
                elif mode == "set":
                    amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                    await set_pooch_breeding_cooldown(
                        pooch_id, amount if not isinstance(cooldown, str) else int(cooldown)
                    )
                else:
                    amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                    await modify_pooch_breeding_cooldown(pooch_id, amount)
                result.pooches_affected.append(pooch_id)

        elif action_type == "rename_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            new_name = parameters.get("name")
            if new_name:
                for pooch_id in pooch_ids:
                    await rename_pooch(pooch_id, str(new_name))
                    result.pooches_affected.append(pooch_id)

        elif action_type == "breed_pooches":
            raw_first_selector = parameters.get("first_pooch_selector", "random")
            first_selector = (
                str(raw_first_selector).strip().lower() if isinstance(raw_first_selector, str) else "random"
            )
            raw_second_selector = parameters.get("second_pooch_selector", "random")
            second_selector = (
                str(raw_second_selector).strip().lower() if isinstance(raw_second_selector, str) else "random"
            )

            first_filter_raw = parameters.get("first_filter", {})
            first_filter = first_filter_raw if isinstance(first_filter_raw, dict) else {}
            second_filter_raw = parameters.get("second_filter", {})
            second_filter = second_filter_raw if isinstance(second_filter_raw, dict) else {}

            # When target_type is "kennel", restrict both parent pools to that kennel's pooches
            breed_kennel_id: int | None = None
            if target_type == "kennel":
                kennel_ids = await _get_target_kennel_ids(target_type, selector, parameters)
                breed_kennel_id = kennel_ids[0] if kennel_ids else None
                if breed_kennel_id is None:
                    logger.warning("breed_pooches: no kennel resolved for kennel target_type; skipping")
                    breed_kennel_id = None  # will skip below

            async def _resolve_breed_pooch_id(sel: str, filt: dict, exclude_id: int | None = None) -> int | None:
                if sel == "selected":
                    pid = context.selected_pooch_id
                    return None if (exclude_id is not None and pid == exclude_id) else pid
                if breed_kennel_id is not None:
                    ids = await list_matching_pooch_ids_in_kennel(owner_discord_id, breed_kennel_id, filt)
                else:
                    ids = await list_matching_pooch_ids(owner_discord_id, filt)
                if exclude_id is not None:
                    ids = [i for i in ids if i != exclude_id]
                return rng.choice(ids) if ids else None

            require_unique = bool(parameters.get("require_unique", True))
            require_same = bool(parameters.get("require_same", False))

            if target_type == "kennel" and breed_kennel_id is None:
                first_pooch_id = None
                second_pooch_id = None
            else:
                first_pooch_id = await _resolve_breed_pooch_id(first_selector, first_filter)
                if require_same:
                    second_pooch_id = first_pooch_id
                else:
                    exclude = first_pooch_id if require_unique else None
                    second_pooch_id = await _resolve_breed_pooch_id(second_selector, second_filter, exclude_id=exclude)

            if first_pooch_id is None or second_pooch_id is None:
                logger.warning("breed_pooches: could not resolve one or both pooches; skipping")
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

            # Resolve delivery kennel when target_type is "kennel"
            buy_kennel_id: int | None = None
            if target_type == "kennel":
                kennel_ids = await _get_target_kennel_ids(target_type, selector, parameters)
                buy_kennel_id = kennel_ids[0] if kennel_ids else None

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

                        if buy_kennel_id is not None:
                            kennel = await get_kennel_by_id(buy_kennel_id)
                            pooches_in = await list_pooches_for_kennel(buy_kennel_id)
                            if kennel is not None and len(pooches_in) < kennel.pooch_limit:
                                await add_pooch_to_kennel(buy_kennel_id, pooch_db.id)
                                dest_key, kennel_name = "kennel", kennel.name
                            else:
                                dest_key, kennel_name = "town", None
                        else:
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
                followup_event = await get_random_eligible_owner_event_for_owner(owner_discord_id, rng=rng)
            else:
                event_name = parameters.get("event")
                followup_event = await db_get_owner_event_by_name(event_name.strip())
                if followup_event is None:
                    logger.warning(f"Unknown event '{event_name}' triggered. Skipping...")
                    result.message = "Error starting followup event."
                    return result

            if followup_event is not None:
                if followup_event.requires_response:
                    # Response-required events run as independent active events but inherit named slots
                    _internal_keys = {"candidate_pooch_ids", "candidate_kennel_ids", "suppressed_option_ids"}
                    slots_to_forward = {
                        k: v for k, v in context.extra_data.items() if not k.startswith("_") and k not in _internal_keys
                    }
                    started_event = await trigger_specific_event(
                        owner_discord_id, followup_event.id, rng=rng, inherited_slots=slots_to_forward
                    )
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
                    # Instant events run inline, sharing the current context so save_as/use_saved slots carry over
                    followup_result = await _execute_event_actions(
                        owner_discord_id, followup_event.actions, context, rng
                    )
                    result.merge(followup_result)
                    default_option = next((opt for opt in followup_event.options if opt.is_default), None)
                    if default_option is not None:
                        option_result = await _execute_event_actions(
                            owner_discord_id, default_option.actions, context, rng
                        )
                        result.merge(option_result)
                        selected_outcome = await _choose_option_outcome(default_option, context, rng)
                        if selected_outcome is not None:
                            outcome_result = await _execute_event_actions(
                                owner_discord_id, selected_outcome.actions, context, rng
                            )
                            result.merge(outcome_result)

        elif action_type == "start_stray_event":
            from src.database import (
                get_stray_event_by_name,
                list_matching_stray_pooch_ids,
            )

            from .manage_stray_events import (
                _choose_stray_event_outcome,
                _execute_stray_event_actions,
            )

            event_name = parameters.get("event")
            if not isinstance(event_name, str) or not event_name.strip():
                logger.warning("start_stray_event: missing 'event' parameter; skipping")
            else:
                stray_event = await get_stray_event_by_name(event_name.strip())
                if stray_event is None:
                    logger.warning(f"start_stray_event: unknown stray event '{event_name}'; skipping")
                else:
                    servers = await list_servers_for_owner(owner_discord_id)
                    if not servers:
                        logger.warning(f"start_stray_event: owner {owner_discord_id} has no servers; skipping")
                    else:
                        server = rng.choice(servers)
                        stray_filter: dict = stray_event.filter or {}
                        pooch_filters = stray_filter.get("pooches", [])
                        if pooch_filters:
                            first_f = {
                                k: v
                                for k, v in pooch_filters[0].items()
                                if k not in {"min_count", "max_count", "description"}
                            }
                            candidate_ids = await list_matching_stray_pooch_ids(server.discord_id, first_f)
                        else:
                            candidate_ids = [p.id for p in await list_strays_for_server(server.discord_id)]
                        stray_context = StrayEventContext(
                            server_discord_id=server.discord_id,
                            candidate_stray_ids=list(candidate_ids),
                        )
                        stray_result = await _execute_stray_event_actions(
                            server.discord_id, stray_event.actions, stray_context, rng
                        )
                        result.merge(stray_result)
                        stray_outcome = await _choose_stray_event_outcome(stray_event, stray_context, rng)
                        if stray_outcome is not None:
                            outcome_result = await _execute_stray_event_actions(
                                server.discord_id, stray_outcome.actions, stray_context, rng
                            )
                            result.merge(outcome_result)

        elif action_type == "select_pooch":
            # Resolves and saves pooches into a named slot; no other side effects
            await _get_target_pooch_ids(target_type, selector, parameters)

        # Stat modify/set actions
        elif action_type in (
            "modify_strength",
            "modify_cuteness",
            "modify_fluffiness",
            "modify_intelligence",
            "modify_dexterity",
            "modify_fertility",
            "modify_aggressiveness",
        ):
            stat = action_type[len("modify_") :]
            modify_fn = {
                "strength": modify_pooch_strength,
                "cuteness": modify_pooch_cuteness,
                "fluffiness": modify_pooch_fluffiness,
                "intelligence": modify_pooch_intelligence,
                "dexterity": modify_pooch_dexterity,
                "fertility": modify_pooch_fertility,
                "aggressiveness": modify_pooch_aggressiveness,
            }[stat]
            set_fn = {
                "strength": set_pooch_strength,
                "cuteness": set_pooch_cuteness,
                "fluffiness": set_pooch_fluffiness,
                "intelligence": set_pooch_intelligence,
                "dexterity": set_pooch_dexterity,
                "fertility": set_pooch_fertility,
                "aggressiveness": set_pooch_aggressiveness,
            }[stat]
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            pre_rolled, roll_once = _resolve_amount(parameters, rng)
            mode = _get_mode(parameters)
            for pooch_id in pooch_ids:
                amount = pre_rolled if roll_once else _get_amount_from_parameters(parameters, rng)
                if mode == "set":
                    pooch = await set_fn(pooch_id, amount)
                else:
                    pooch = await modify_fn(pooch_id, amount)
                if pooch:
                    result.pooches_affected.append(pooch_id)

        # Hell / soul actions
        elif action_type == "damn_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            for pooch_id in pooch_ids:
                pooch = await get_pooch_by_id(pooch_id)
                if pooch:
                    await set_pooch_dead(pooch_id)
                    await damn_pooch(pooch_id)
                    result.pooches_killed.append(pooch_id)
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = (
                    "A pooch has been damned to Hell!" if count == 1 else f"{count} pooches have been damned to Hell!"
                )

        elif action_type == "revive_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            destination_str = str(parameters.get("destination", "kennel")).strip().lower()
            for pooch_id in pooch_ids:
                pooch = await revive_pooch(pooch_id)
                if pooch:
                    dest_key, kennel_name = await _deliver_pooch(owner_discord_id, pooch_id, destination_str)
                    result.pooches_affected.append(pooch_id)
                    if dest_key == "kennel":
                        result.message = f"{pooch.name} has been revived and placed in {kennel_name}!"
                    elif dest_key == "hell":
                        result.message = f"{pooch.name} has been revived and sent back to Hell..."
                    elif dest_key == "graveyard":
                        result.message = f"{pooch.name} has been revived and placed in the graveyard."
                    else:
                        result.message = f"{pooch.name} has been revived!"
                    save_as = parameters.get("save_as")
                    if isinstance(save_as, str) and save_as:
                        context.extra_data.setdefault(save_as, {}).setdefault("pooch_ids", []).append(pooch_id)

        elif action_type == "conjure_pooch":
            # Create a new pooch from Hell ritual — does NOT charge bloodskulls (handle with modify_bloodskulls)
            num_rolls = int(parameters.get("num_rolls", 1))
            num_rolls = max(1, num_rolls)
            destination_str = str(parameters.get("destination", "kennel")).strip().lower()

            conjured: Any = None
            for _ in range(num_rolls):
                pooch = await create_pooch(
                    owner_discord_id=owner_discord_id,
                    age=0,
                    base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
                    **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
                    rng=rng,
                )
                num_breeds = rng.randint(NUM_BREEDS_PER_SUMMON_POOCH_RANGE[0], NUM_BREEDS_PER_SUMMON_POOCH_RANGE[1])
                for _ in range(num_breeds):
                    await add_breed_to_pooch(pooch.id, weight=(1.0 / num_breeds), from_ritual=True, rng=rng)

                if conjured is None or (
                    await get_pooch_bloodskull_value(pooch.id) > await get_pooch_bloodskull_value(conjured.id)
                ):
                    if conjured is not None:
                        await delete_pooch(conjured.id)
                    conjured = pooch
                else:
                    await delete_pooch(pooch.id)

            if conjured:
                mark = await get_mutation_by_name("Mark of the Beast")
                if mark is not None:
                    await add_mutation_to_pooch(conjured.id, mutation_id=mark.id)

                dest_key, kennel_name = await _deliver_pooch(owner_discord_id, conjured.id, destination_str)
                context.selected_pooch_id = conjured.id
                candidate_pooch_ids = context.extra_data.setdefault("candidate_pooch_ids", [])
                if isinstance(candidate_pooch_ids, list) and conjured.id not in candidate_pooch_ids:
                    candidate_pooch_ids.append(conjured.id)
                if conjured.id not in context.affected_pooch_ids:
                    context.affected_pooch_ids.append(conjured.id)
                result.pooches_created.append(conjured.id)
                result.pooches_affected.append(conjured.id)
                if dest_key == "kennel":
                    result.message = f"{conjured.name} was conjured and placed in {kennel_name}!"
                else:
                    result.message = f"{conjured.name} was conjured!"
                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as:
                    context.extra_data[save_as] = {"pooch_ids": [conjured.id]}

        elif action_type == "sacrifice_pooch":
            pooch_ids = await _get_target_pooch_ids(target_type, selector, parameters)
            value_multiplier = parameters.get("value_multiplier")
            multiplier = float(value_multiplier) if isinstance(value_multiplier, (int, float)) else 1.0
            for pooch_id in pooch_ids:
                pooch = await get_pooch_by_id(pooch_id)
                if pooch is None or not pooch.alive:
                    continue
                value = round((await get_pooch_bloodskull_value(pooch_id)) * multiplier)
                await give_bloodskulls_to_owner(owner_discord_id, value)
                await give_bones_to_owner(owner_discord_id, 1)
                await set_pooch_dead(pooch_id)
                await remove_pooch_from_kennel(pooch_id)
                await damn_pooch(pooch_id)
                result.bloodskulls_changed += value
                result.pooches_killed.append(pooch_id)
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = (
                    "A pooch has been sacrificed!" if count == 1 else f"{count} pooches have been sacrificed!"
                )

        else:
            logger.warning(f"Unknown action type: {action_type}")

    except Exception as e:
        logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
        result.success = False
        result.message = f"Error: {str(e)}"

    return result


async def _execute_event_actions(
    owner_discord_id: int, actions: list[EventAction], context: OwnerEventContext, rng: random.Random
) -> OwnerEventResult:
    """
    Execute a list of event actions.
    """

    result = OwnerEventResult()

    for action in sorted(actions, key=lambda a: a.action_order):
        repeat = max(int(action.repeat), 1) if isinstance(action.repeat, int) else 1
        for _ in range(repeat):
            action_result = await _execute_single_action(owner_discord_id, action, context, rng)
            result.merge(action_result)

    return result


async def _create_and_execute_event(
    owner_discord_id: int,
    event: EventDB,
    rng: random.Random,
    inherited_slots: Optional[dict] = None,
) -> Optional[TriggeredOwnerEvent]:
    """
    Create an active event and execute it if it doesn't require a response.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    event: OwnerEvent
        The event to trigger.

    rng: Random
        Random number generator.

    Returns
    -------
    TriggeredOwnerEvent, optional
        The triggered event, or None if creation failed.
    """

    context = await _create_event_context(owner_discord_id, event, rng)
    if inherited_slots:
        context.extra_data.update(inherited_slots)

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

    # OwnerEvent-level actions always fire immediately at trigger time (before the user picks)
    result = await _execute_event_actions(owner_discord_id, event.actions, context, rng)
    await update_active_event_result(active_event.id, result.to_dict())

    # Preflight: pre-resolve exclude_claimed targets for visible options so that each option
    # gets a unique pooch and options with no valid target are suppressed.
    if event.requires_response:
        claimed_ids: set[int] = set()
        suppressed_option_ids: list[int] = []

        for option in sorted(event.options, key=lambda o: o.option_order):
            if not option.is_visible:
                continue
            option_suppressed = False
            for action_order, action in enumerate(sorted(option.actions, key=lambda a: a.action_order)):
                if not action.parameters.get("exclude_claimed", False):
                    continue
                # Resolve candidate pooch IDs for this action, excluding already-claimed IDs
                action_filter_raw = action.parameters.get("filter", {})
                action_filter_spec = action_filter_raw if isinstance(action_filter_raw, dict) else {}
                try:
                    candidate_ids = await list_matching_pooch_ids(owner_discord_id, action_filter_spec)
                    candidate_ids = [pid for pid in candidate_ids if pid not in claimed_ids]
                except Exception:
                    candidate_ids = []

                if not candidate_ids:
                    option_suppressed = True
                    break
                chosen_id = rng.choice(candidate_ids)
                claimed_ids.add(chosen_id)
                slot_key = f"_claimed_{option.id}_{action_order}"
                context.extra_data[slot_key] = chosen_id

            if option_suppressed:
                suppressed_option_ids.append(option.id)

        if suppressed_option_ids:
            context.extra_data["suppressed_option_ids"] = suppressed_option_ids

    # Persist the updated context so named slots written by trigger-time actions
    # (via save_as) survive to response/expiry time when context is reloaded from DB.
    if event.requires_response:
        await update_active_event_context(active_event.id, context.to_dict())

    if not event.requires_response:
        await archive_active_event(active_event.id)

    active_event.result_summary = result.to_dict()
    active_event.context = context.to_dict()
    active_event.expires_at = expires_at
    return await to_triggered_owner_event(active_event)


async def trigger_random_event(
    owner_discord_id: int, rng: Optional[random.Random] = None
) -> Optional[TriggeredOwnerEvent]:
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
    TriggeredOwnerEvent, optional
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
    owner_discord_id: int,
    event_id: int,
    rng: Optional[random.Random] = None,
    inherited_slots: Optional[dict] = None,
) -> Optional[TriggeredOwnerEvent]:
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
    TriggeredOwnerEvent, optional
        The triggered event, or None if the event couldn't be triggered.
    """

    if rng is None:
        rng = random.Random()

    event = await db_get_owner_event_by_id(event_id)
    if event is None:
        logger.warning(f"OwnerEvent {event_id} not found")
        return None

    return await _create_and_execute_event(owner_discord_id, event, rng, inherited_slots=inherited_slots)


async def trigger_event_by_name(
    owner_discord_id: int, event_name: str, rng: Optional[random.Random] = None
) -> Optional[TriggeredOwnerEvent]:
    """
    Trigger a specific event for an owner by its name.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    event_name: str
        The name of the event to trigger.

    rng: Random, optional
        Random number generator for reproducibility.

    Returns
    -------
    TriggeredOwnerEvent, optional
        The triggered event, or None if the event couldn't be found or triggered.
    """
    event = await db_get_owner_event_by_name(event_name)
    if event is None:
        logger.warning(f"OwnerEvent '{event_name}' not found")
        return None

    return await trigger_specific_event(owner_discord_id, event.id, rng)
