"""
Server event triggering, resolution, and the daily event cycle.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.database import (
    check_server_event_filter_for_server,
    create_server_event_occurrence,
    finalize_server_event_participation,
    get_active_server_event_occurrence_by_tier,
    get_current_season,
    get_server_by_discord_id,
)
from src.database import get_server_event_by_name as db_get_server_event_by_name
from src.database import (
    get_server_event_occurrence_by_id,
    list_active_server_event_occurrences,
    list_kennels_for_owner,
    list_owner_discord_ids_for_server,
    list_pooches_for_kennel,
    list_server_events_with_weights_by_tier,
    list_servers,
    resolve_server_event_occurrence,
)
from src.database.utils import rarity_choice
from src.game.events.owner_events import (
    execute_event_actions as _execute_owner_event_actions,
)
from src.game.models.events import (
    OwnerEventContext,
    OwnerEventResult,
    ServerEventContext,
    ServerEventResolution,
    TriggeredServerEvent,
    to_triggered_server_event,
)
from src.logger import get_logger

from .actions import execute_server_actions
from .arena import resolve_arena_matchups
from .scoring import rank_participations

logger = get_logger("game/events/server_events/coordinator")

SERVER_EVENT_DURATION = timedelta(days=1)
MAJOR_SERVER_EVENT_DURATION = timedelta(days=7)
MINOR_EVENT_DAILY_CHANCE = 0.5


def roll_outcome_chance(chance: float | None, rng: random.Random) -> bool:
    """
    Roll outcome chance.

    Parameters
    ----------
    chance: Any
        The `chance` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `roll_outcome_chance`.
    """

    if chance is None:
        return True
    return rng.random() <= float(chance)


def matches_rank(min_rank: int | None, max_rank: int | None, rank: int | None) -> bool:
    """
    Matches rank.

    Parameters
    ----------
    min_rank: Any
        The `min_rank` value.

    max_rank: Any
        The `max_rank` value.

    rank: Any
        The `rank` value.

    Returns
    -------
    Any
        The result of calling `matches_rank`.
    """

    if rank is None:
        return min_rank is None and max_rank is None
    if min_rank is not None and rank < min_rank:
        return False
    if max_rank is not None and rank > max_rank:
        return False
    return True


async def build_owner_event_context(owner_discord_id: int, selected_pooch_id: int | None = None) -> OwnerEventContext:
    """
    Build owner event context.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    selected_pooch_id: Any
        The `selected_pooch_id` value.

    Returns
    -------
    Any
        The result of calling `build_owner_event_context`.
    """

    context = OwnerEventContext(owner_discord_id=owner_discord_id)
    kennels = await list_kennels_for_owner(owner_discord_id)
    candidate_kennel_ids = [kennel.id for kennel in kennels]
    candidate_pooch_ids: list[int] = []
    for kennel in kennels:
        pooches = await list_pooches_for_kennel(kennel.id)
        candidate_pooch_ids.extend([pooch.id for pooch in pooches if pooch.alive])
    context.extra_data["candidate_kennel_ids"] = candidate_kennel_ids
    context.extra_data["candidate_pooch_ids"] = candidate_pooch_ids
    if selected_pooch_id is not None:
        context.selected_pooch_id = selected_pooch_id
        if selected_pooch_id not in context.affected_pooch_ids:
            context.affected_pooch_ids.append(selected_pooch_id)
    return context


async def _check_server_filter(server_discord_id: int, filter_spec: dict | None, season: Optional[str] = None) -> bool:
    return await check_server_event_filter_for_server(server_discord_id, filter_spec, season=season)


async def trigger_daily_server_event(
    server_discord_id: int,
    tier: str = "minor",
    rng: Optional[random.Random] = None,
) -> TriggeredServerEvent | None:
    """
    Trigger daily server event.

    Parameters
    ----------
    server_discord_id: Any
        The `server_discord_id` value.

    tier: Any
        The `tier` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `trigger_daily_server_event`.
    """

    rng = rng if rng is not None else random.Random()
    tier = tier.strip().lower()
    existing = await get_active_server_event_occurrence_by_tier(server_discord_id, tier)
    if existing is not None:
        return await to_triggered_server_event(existing)

    server = await get_server_by_discord_id(server_discord_id)
    if server is None or server.event_channel_discord_id is None:
        return None

    events_with_weights = await list_server_events_with_weights_by_tier(tier)
    eligible: list[tuple] = []
    for event_obj, rarity in events_with_weights:
        filter_spec = event_obj.filter or {}
        if await _check_server_filter(server_discord_id, filter_spec, season=await get_current_season()):
            eligible.append((event_obj, rarity))

    if not eligible:
        return None

    server_event = rarity_choice(rng, eligible)
    if server_event is None:
        return None

    server_context = ServerEventContext(server_discord_id=server_discord_id)
    if server_event.actions:
        server_actions = [a for a in server_event.actions if a.target_type == "server"]
        if server_actions:
            action_dicts = [{"action_type": a.action_type, "parameters": a.parameters or {}} for a in server_actions]
            await execute_server_actions(
                server_discord_id, action_dicts, server_context, rng, season=await get_current_season()
            )

    duration = MAJOR_SERVER_EVENT_DURATION if tier == "major" else SERVER_EVENT_DURATION
    occurrence = await create_server_event_occurrence(
        server_discord_id=server_discord_id,
        server_event_id=server_event.id,
        context=server_context.to_dict(),
        expires_at=datetime.now(timezone.utc) + duration,
    )
    hydrated = await get_server_event_occurrence_by_id(occurrence.id)
    if hydrated is None:
        return None
    logger.info("Triggered %s server event '%s' for server %s", tier, server_event.name, server_discord_id)
    return await to_triggered_server_event(hydrated)


async def trigger_server_event_by_name(
    server_discord_id: int,
    name: str,
    rng: Optional[random.Random] = None,
) -> TriggeredServerEvent | None:
    """Trigger a specific server event by name, bypassing random selection and filter checks."""
    rng = rng if rng is not None else random.Random()
    server_event = await db_get_server_event_by_name(name)
    if server_event is None:
        return None

    tier = getattr(server_event, "tier", "minor").strip().lower()
    existing = await get_active_server_event_occurrence_by_tier(server_discord_id, tier)
    if existing is not None:
        return await to_triggered_server_event(existing)

    server = await get_server_by_discord_id(server_discord_id)
    if server is None or server.event_channel_discord_id is None:
        return None

    server_context = ServerEventContext(server_discord_id=server_discord_id)
    if server_event.actions:
        server_actions = [a for a in server_event.actions if a.target_type == "server"]
        if server_actions:
            action_dicts = [{"action_type": a.action_type, "parameters": a.parameters or {}} for a in server_actions]
            await execute_server_actions(
                server_discord_id, action_dicts, server_context, rng, season=await get_current_season()
            )

    duration = MAJOR_SERVER_EVENT_DURATION if tier == "major" else SERVER_EVENT_DURATION
    occurrence = await create_server_event_occurrence(
        server_discord_id=server_discord_id,
        server_event_id=server_event.id,
        context=server_context.to_dict(),
        expires_at=datetime.now(timezone.utc) + duration,
    )
    hydrated = await get_server_event_occurrence_by_id(occurrence.id)
    if hydrated is None:
        return None
    logger.info("Dev-triggered server event '%s' for server %s", name, server_discord_id)
    return await to_triggered_server_event(hydrated)


async def resolve_server_event(
    occurrence_id: int,
    rng: Optional[random.Random] = None,
) -> ServerEventResolution | None:
    """
    Resolve server event.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `resolve_server_event`.
    """

    rng = rng if rng is not None else random.Random()
    occurrence = await get_server_event_occurrence_by_id(occurrence_id)
    if occurrence is None or occurrence.archived or occurrence.resolved_at is not None:
        return None

    server_discord_id = occurrence.server_discord_id
    server_context = ServerEventContext.from_dict(occurrence.context or {})
    server_event = occurrence.server_event
    _season = await get_current_season()

    await resolve_arena_matchups(occurrence.id, server_context, server_event.parameters or {}, rng)
    ranked_participations = await rank_participations(occurrence, rng)
    winner_owner_ids: list[int] = []
    winner_pooch_ids: list[int] = []

    if not ranked_participations:
        default_actions = list(server_event.default_actions_data or [])
        if default_actions:
            await execute_server_actions(server_discord_id, default_actions, server_context, rng, season=_season)
    else:
        for participation, score, rank in ranked_participations:
            context = OwnerEventContext.from_dict(participation.context or {})
            combined_result = (
                OwnerEventResult.from_dict(participation.resolution_result or {})
                if participation.resolution_result
                else OwnerEventResult()
            )
            matched_messages: list[str] = []

            for outcome in sorted(server_event.outcomes, key=lambda v: v.outcome_order):
                outcome_target = str(outcome.target or "ranked_players").strip().lower()

                if outcome_target == "ranked_players":
                    if not matches_rank(outcome.min_rank, outcome.max_rank, rank):
                        continue
                elif outcome_target == "all_participants":
                    pass
                elif outcome_target == "non_participants":
                    continue
                elif outcome_target == "server":
                    continue

                if not roll_outcome_chance(outcome.chance, rng):
                    continue

                outcome_result = await _execute_owner_event_actions(
                    participation.owner_discord_id, outcome.actions, context, rng
                )
                if outcome.message:
                    outcome_result.message = outcome.message
                    matched_messages.append(outcome.message)
                combined_result.merge(outcome_result)

            if matched_messages and not combined_result.message:
                combined_result.message = matched_messages[-1]

            await finalize_server_event_participation(
                participation.id,
                resolution_result=combined_result.to_dict(),
                score=score,
                rank=rank,
            )
            if rank == 1:
                winner_owner_ids.append(participation.owner_discord_id)
                for sub in list(participation.submissions or []):
                    pid = sub.get("selected_pooch_id")
                    if pid is not None and pid not in winner_pooch_ids:
                        winner_pooch_ids.append(pid)
                        break

        participant_owner_ids = {p.owner_discord_id for p, _, _ in ranked_participations}
        for outcome in sorted(server_event.outcomes, key=lambda v: v.outcome_order):
            outcome_target = str(outcome.target or "ranked_players").strip().lower()
            if outcome_target not in ("server", "non_participants"):
                continue
            if not roll_outcome_chance(outcome.chance, rng):
                continue

            if outcome_target == "server":
                action_dicts = [
                    {"action_type": a.action_type, "parameters": a.parameters or {}} for a in outcome.actions
                ]
                await execute_server_actions(server_discord_id, action_dicts, server_context, rng, season=_season)

            elif outcome_target == "non_participants":
                all_server_owner_ids = await list_owner_discord_ids_for_server(server_discord_id)

                for oid in all_server_owner_ids:
                    if oid not in participant_owner_ids:
                        non_ctx = await build_owner_event_context(oid)
                        await _execute_owner_event_actions(oid, outcome.actions, non_ctx, rng)

    summary = OwnerEventResult(
        message=(
            f"Resolved '{server_event.name}' with {len(ranked_participations)} participant"
            f"{'s' if len(ranked_participations) != 1 else ''}."
        )
    )
    summary.extra_data["winner_owner_ids"] = winner_owner_ids
    summary.extra_data["winner_pooch_ids"] = winner_pooch_ids
    summary.extra_data["participant_count"] = len(ranked_participations)

    await resolve_server_event_occurrence(occurrence_id, result_summary=summary.to_dict())

    return ServerEventResolution(
        occurrence_id=occurrence.id,
        server_discord_id=server_discord_id,
        name=server_event.name,
        participant_count=len(ranked_participations),
        winner_owner_ids=winner_owner_ids,
        winner_pooch_ids=winner_pooch_ids,
        result_summary=summary,
    )


async def run_daily_server_event_cycle(
    rng: Optional[random.Random] = None,
) -> tuple[dict[int, TriggeredServerEvent], list[ServerEventResolution]]:
    """Resolve expired events and roll for a new minor server event on each server."""
    rng = rng if rng is not None else random.Random()

    resolutions: list[ServerEventResolution] = []
    active_occurrences = await list_active_server_event_occurrences()
    for occurrence in active_occurrences:
        resolution = await resolve_server_event(occurrence.id, rng)
        if resolution is not None:
            resolutions.append(resolution)

    new_events: dict[int, TriggeredServerEvent] = {}
    servers = await list_servers()

    for server in servers:
        if server.event_channel_discord_id is None:
            continue
        if rng.random() < MINOR_EVENT_DAILY_CHANCE:
            event = await trigger_daily_server_event(server.discord_id, tier="minor", rng=rng)
            if event is not None:
                new_events[server.discord_id] = event

    return new_events, resolutions


async def run_weekly_server_event_cycle(
    rng: Optional[random.Random] = None,
    new_season: Optional[str] = None,
) -> tuple[dict[int, TriggeredServerEvent], list[ServerEventResolution], dict[int, str]]:
    """Resolve expired major events, trigger a new major event, and build season_advances."""
    rng = rng if rng is not None else random.Random()

    resolutions: list[ServerEventResolution] = []
    active_occurrences = await list_active_server_event_occurrences()
    for occurrence in active_occurrences:
        resolution = await resolve_server_event(occurrence.id, rng)
        if resolution is not None:
            resolutions.append(resolution)

    servers = await list_servers()
    season_advances: dict[int, str] = {}
    if new_season is not None:
        season_advances = {
            server.discord_id: new_season for server in servers if server.event_channel_discord_id is not None
        }

    new_events: dict[int, TriggeredServerEvent] = {}
    for server in servers:
        if server.event_channel_discord_id is None:
            continue
        event = await trigger_daily_server_event(server.discord_id, tier="major", rng=rng)
        if event is not None:
            new_events[server.discord_id] = event

    return new_events, resolutions, season_advances
