from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.database.models import ServerEventOccurrence as ServerEventOccurrenceORM

from .event_result import EventResult
from .server_event_context import ServerEventContext
from .server_event_option import ServerEventOption, to_server_event_option
from .server_event_participation import (
    ServerEventParticipationSummary,
    to_server_event_participation_summary,
)


@dataclass
class TriggeredServerEvent:
    occurrence_id: int
    event_id: int
    server_discord_id: int
    name: str
    category: str
    description: str
    flavor_text: str
    severity: str
    expires_at: datetime
    context: ServerEventContext
    options: list[ServerEventOption] = field(default_factory=list)
    participation_count: int = 0
    max_participants: int = 0
    message_discord_id: int | None = None
    viewer_participation: ServerEventParticipationSummary | None = None
    result_summary: EventResult | None = None


async def to_triggered_server_event(
    occurrence: ServerEventOccurrenceORM,
    viewer_owner_discord_id: int | None = None,
) -> TriggeredServerEvent:
    event = occurrence.server_event
    viewer_participation = None
    if viewer_owner_discord_id is not None:
        for participation in occurrence.participations:
            if participation.owner_discord_id == viewer_owner_discord_id:
                viewer_participation = await to_server_event_participation_summary(participation)
                break

    return TriggeredServerEvent(
        occurrence_id=occurrence.id,
        event_id=event.id,
        server_discord_id=occurrence.server_discord_id,
        name=event.name,
        category=event.category,
        description=event.description,
        flavor_text=event.flavor_text,
        severity=event.severity,
        expires_at=occurrence.expires_at,
        context=ServerEventContext.from_dict(occurrence.context or {}),
        options=[
            await to_server_event_option(option)
            for option in sorted(event.options, key=lambda value: value.option_order)
        ],
        participation_count=len(occurrence.participations),
        max_participants=event.max_participants,
        message_discord_id=occurrence.message_discord_id,
        viewer_participation=viewer_participation,
        result_summary=EventResult.from_dict(occurrence.result_summary or {}) if occurrence.result_summary else None,
    )
