from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from database.models import ServerEventParticipation as ServerEventParticipationORM

from .event_context import EventContext
from .event_entity_reference import (
    EventEntityReferences,
    resolve_event_entity_references,
)
from .event_result import EventResult
from .server_event_option import ServerEventOption, to_server_event_option


@dataclass
class ServerEventParticipationSummary:
    owner_discord_id: int
    selected_option: ServerEventOption
    context: EventContext
    immediate_result: EventResult | None = None
    resolution_result: EventResult | None = None
    score: float | None = None
    rank: int | None = None
    participated_at: datetime | None = None
    entity_references: EventEntityReferences = field(default_factory=EventEntityReferences)


async def to_server_event_participation_summary(
    participation: ServerEventParticipationORM,
) -> ServerEventParticipationSummary:
    context = EventContext.from_dict(participation.context or {})
    immediate_result = (
        EventResult.from_dict(participation.immediate_result or {}) if participation.immediate_result else None
    )
    resolution_result = (
        EventResult.from_dict(participation.resolution_result or {}) if participation.resolution_result else None
    )
    entity_references = await resolve_event_entity_references(context, resolution_result or immediate_result)
    return ServerEventParticipationSummary(
        owner_discord_id=participation.owner_discord_id,
        selected_option=await to_server_event_option(participation.selected_option),
        context=context,
        immediate_result=immediate_result,
        resolution_result=resolution_result,
        score=participation.score,
        rank=participation.rank,
        participated_at=participation.participated_at,
        entity_references=entity_references,
    )
