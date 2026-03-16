from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.database.models import ServerEventParticipation as ServerEventParticipationORM

from ..owner_events.owner_event_context import OwnerEventContext
from ..owner_events.owner_event_entity_reference import (
    OwnerEventEntityReferences,
    resolve_owner_event_entity_references,
)
from ..owner_events.owner_event_result import OwnerEventResult
from .server_event_option import ServerEventOption, to_server_event_option


@dataclass
class ServerEventParticipationSummary:
    owner_discord_id: int
    selected_option: ServerEventOption
    context: OwnerEventContext
    immediate_result: OwnerEventResult | None = None
    resolution_result: OwnerEventResult | None = None
    score: float | None = None
    rank: int | None = None
    participated_at: datetime | None = None
    entity_references: OwnerEventEntityReferences = field(default_factory=OwnerEventEntityReferences)


async def to_server_event_participation_summary(
    participation: ServerEventParticipationORM,
) -> ServerEventParticipationSummary:
    context = OwnerEventContext.from_dict(participation.context or {})
    immediate_result = (
        OwnerEventResult.from_dict(participation.immediate_result or {}) if participation.immediate_result else None
    )
    resolution_result = (
        OwnerEventResult.from_dict(participation.resolution_result or {}) if participation.resolution_result else None
    )
    entity_references = await resolve_owner_event_entity_references(context, resolution_result or immediate_result)
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
