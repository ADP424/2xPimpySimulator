from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from src.database import (
    create_server_event_occurrence,
    create_server_event_participation,
    finalize_server_event_participation,
    get_active_server_event_occurrence,
    get_owner_by_discord_id,
    get_owner_server,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_random_eligible_server_event_for_server,
    get_server_by_discord_id,
    get_server_event_occurrence_by_id,
    get_server_event_option_by_id,
    get_server_event_participation,
    list_active_server_event_occurrences,
    list_kennels_for_owner,
    list_pooches_for_kennel,
    list_servers,
    resolve_server_event_occurrence,
    set_server_event_occurrence_message_discord_id,
)
from src.logger import get_logger

from .manage_events import _execute_event_actions
from .manage_owners import get_or_create_owner
from .models.events import (
    EventContext,
    EventResult,
    ServerEventContext,
    ServerEventParticipationSummary,
    ServerEventResolution,
    TriggeredServerEvent,
    to_server_event_participation_summary,
    to_triggered_server_event,
)

if TYPE_CHECKING:
    from src.database.models import ServerEventOccurrence, ServerEventParticipation

logger = get_logger("game/manage_server_events")

SERVER_EVENT_DURATION = timedelta(days=1)


def _roll_outcome_chance(chance: float | None, rng: random.Random) -> bool:
    if chance is None:
        return True
    return rng.random() <= float(chance)


def _matches_rank(min_rank: int | None, max_rank: int | None, rank: int | None) -> bool:
    if rank is None:
        return min_rank is None and max_rank is None
    if min_rank is not None and rank < min_rank:
        return False
    if max_rank is not None and rank > max_rank:
        return False
    return True


async def _build_owner_event_context(owner_discord_id: int, selected_pooch_id: int | None = None) -> EventContext:
    context = EventContext(owner_discord_id=owner_discord_id)
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


async def _compute_participation_score(
    participation: ServerEventParticipation, strategy: str, rng: random.Random
) -> float:
    if strategy == "selected_pooch_health":
        context = EventContext.from_dict(participation.context or {})
        if context.selected_pooch_id is not None:
            pooch = await db_get_pooch_by_id(context.selected_pooch_id)
            if pooch is not None:
                return float(pooch.base_health)
        return 0.0

    if strategy == "participation_only":
        return 0.0

    return rng.random()


async def _rank_participations(
    occurrence: ServerEventOccurrence, rng: random.Random
) -> list[tuple[ServerEventParticipation, float, int]]:
    strategy = str(occurrence.server_event.resolution_strategy or "random_winner").strip().lower()
    scored: list[tuple[ServerEventParticipation, float, float]] = []
    for participation in occurrence.participations:
        score = await _compute_participation_score(participation, strategy, rng)
        tie_breaker = rng.random()
        scored.append((participation, score, tie_breaker))

    if strategy == "participation_only":
        ordered = sorted(scored, key=lambda item: item[0].participated_at)
    else:
        ordered = sorted(scored, key=lambda item: (item[1], item[2]), reverse=True)

    return [(participation, score, index + 1) for index, (participation, score, _tie) in enumerate(ordered)]


async def trigger_daily_server_event(
    server_discord_id: int, rng: Optional[random.Random] = None
) -> TriggeredServerEvent | None:
    rng = rng if rng is not None else random.Random()

    existing = await get_active_server_event_occurrence(server_discord_id)
    if existing is not None:
        return await to_triggered_server_event(existing)

    server = await get_server_by_discord_id(server_discord_id)
    if server is None or server.event_channel_discord_id is None:
        return None

    server_event = await get_random_eligible_server_event_for_server(server_discord_id, rng=rng)
    if server_event is None:
        return None

    occurrence = await create_server_event_occurrence(
        server_discord_id=server_discord_id,
        server_event_id=server_event.id,
        context=ServerEventContext(server_discord_id=server_discord_id).to_dict(),
        expires_at=datetime.now(timezone.utc) + SERVER_EVENT_DURATION,
    )
    hydrated = await get_server_event_occurrence_by_id(occurrence.id)
    if hydrated is None:
        return None
    logger.info("Triggered server event '%s' for server %s", server_event.name, server_discord_id)
    return await to_triggered_server_event(hydrated)


async def get_active_server_event(
    server_discord_id: int, viewer_owner_discord_id: int | None = None
) -> TriggeredServerEvent | None:
    occurrence = await get_active_server_event_occurrence(server_discord_id)
    if occurrence is None:
        return None
    return await to_triggered_server_event(occurrence, viewer_owner_discord_id)


async def list_active_server_events() -> list[TriggeredServerEvent]:
    occurrences = await list_active_server_event_occurrences()
    return [await to_triggered_server_event(occurrence) for occurrence in occurrences]


async def participate_in_server_event(
    occurrence_id: int,
    server_discord_id: int,
    owner_discord_id: int,
    option_id: int,
    selected_pooch_id: int | None = None,
    rng: Optional[random.Random] = None,
) -> tuple[bool, str, ServerEventParticipationSummary | None]:
    rng = rng if rng is not None else random.Random()

    occurrence = await get_server_event_occurrence_by_id(occurrence_id)
    if occurrence is None or occurrence.server_discord_id != server_discord_id:
        return False, "Server event not found.", None
    if occurrence.archived or occurrence.resolved_at is not None:
        return False, "This server event has already resolved.", None
    if datetime.now(timezone.utc) > occurrence.expires_at:
        return False, "This server event has already expired.", None

    await get_or_create_owner(server_discord_id, owner_discord_id)
    owner_server = await get_owner_server(server_discord_id, owner_discord_id)
    if owner_server is None:
        return False, "You must be registered in this server first.", None

    existing = await get_server_event_participation(occurrence_id, owner_discord_id)
    if existing is not None:
        return False, "You have already participated in this server event.", None

    option = await get_server_event_option_by_id(option_id)
    if option is None or option.server_event_id != occurrence.server_event_id:
        return False, "That option is not valid for this server event.", None

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", None
    if owner.dollars < option.min_money:
        return False, f"You need at least ${option.min_money} to choose that option.", None
    if owner.bloodskulls < option.min_bloodskulls:
        return False, f"You need at least {option.min_bloodskulls} bloodskulls to choose that option.", None

    current_count = len(occurrence.participations)
    max_participants = occurrence.server_event.max_participants
    if max_participants > 0 and current_count >= max_participants:
        return False, "This server event is already full.", None

    context = await _build_owner_event_context(owner_discord_id, selected_pooch_id)

    if option.requires_pooch_selection:
        if selected_pooch_id is None:
            return False, "You must select a pooch for that option.", None
        pooch = await db_get_pooch_by_id(selected_pooch_id)
        if pooch is None or pooch.owner_discord_id != owner_discord_id or not pooch.alive:
            return False, "That pooch is not a valid choice.", None

    immediate_result = await _execute_event_actions(owner_discord_id, option.actions, context, rng)
    await create_server_event_participation(
        occurrence_id=occurrence_id,
        owner_discord_id=owner_discord_id,
        selected_option_id=option.id,
        context=context.to_dict(),
        immediate_result=immediate_result.to_dict(),
    )
    hydrated = await get_server_event_participation(occurrence_id, owner_discord_id)
    if hydrated is None:
        return False, "Failed to save your participation.", None

    summary = await to_server_event_participation_summary(hydrated)
    return True, f"You joined {occurrence.server_event.name}!", summary


async def resolve_server_event(
    occurrence_id: int,
    rng: Optional[random.Random] = None,
) -> ServerEventResolution | None:
    rng = rng if rng is not None else random.Random()
    occurrence = await get_server_event_occurrence_by_id(occurrence_id)
    if occurrence is None or occurrence.archived or occurrence.resolved_at is not None:
        return None

    ranked_participations = await _rank_participations(occurrence, rng)
    winner_owner_ids: list[int] = []
    winner_pooch_ids: list[int] = []

    for participation, score, rank in ranked_participations:
        context = EventContext.from_dict(participation.context or {})
        combined_result = (
            EventResult.from_dict(participation.resolution_result or {})
            if participation.resolution_result
            else EventResult()
        )
        matched_messages: list[str] = []

        for outcome in sorted(occurrence.server_event.outcomes, key=lambda value: value.outcome_order):
            if not _matches_rank(outcome.min_rank, outcome.max_rank, rank):
                continue
            if not _roll_outcome_chance(outcome.chance, rng):
                continue
            outcome_result = await _execute_event_actions(participation.owner_discord_id, outcome.actions, context, rng)
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
            if context.selected_pooch_id is not None:
                winner_pooch_ids.append(context.selected_pooch_id)

    summary = EventResult(
        message=(
            f"Resolved '{occurrence.server_event.name}' with {len(ranked_participations)} participant"
            f"{'s' if len(ranked_participations) != 1 else ''}."
        )
    )
    summary.extra_data["winner_owner_ids"] = winner_owner_ids
    summary.extra_data["winner_pooch_ids"] = winner_pooch_ids
    summary.extra_data["participant_count"] = len(ranked_participations)

    await resolve_server_event_occurrence(occurrence_id, result_summary=summary.to_dict())

    return ServerEventResolution(
        occurrence_id=occurrence.id,
        server_discord_id=occurrence.server_discord_id,
        name=occurrence.server_event.name,
        participant_count=len(ranked_participations),
        winner_owner_ids=winner_owner_ids,
        winner_pooch_ids=winner_pooch_ids,
        result_summary=summary,
    )


async def run_daily_server_event_cycle(
    rng: Optional[random.Random] = None,
) -> tuple[dict[int, TriggeredServerEvent], list[ServerEventResolution]]:
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
        event = await trigger_daily_server_event(server.discord_id, rng)
        if event is not None:
            new_events[server.discord_id] = event

    return new_events, resolutions


async def set_server_event_message_id(occurrence_id: int, message_discord_id: int | None) -> None:
    await set_server_event_occurrence_message_discord_id(occurrence_id, message_discord_id)
