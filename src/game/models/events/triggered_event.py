from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.database import get_owner_event_by_id

from .event_context import EventContext
from .event_entity_reference import (
    EventEntityReferences,
    resolve_event_entity_references,
)
from .event_option import EventOption, to_event_option
from .event_result import EventResult

if TYPE_CHECKING:
    from src.database.models import EventOccurrence as EventOccurrenceORM


@dataclass
class TriggeredEvent:
    active_owner_event_id: int
    event_id: int

    name: str
    category: str
    description: str
    flavor_text: str
    severity: str

    requires_response: bool
    response_timeout: int
    expires_at: datetime | None

    context: EventContext
    options: list[EventOption] = field(default_factory=list)
    result: EventResult | None = None
    entity_references: EventEntityReferences = field(default_factory=EventEntityReferences)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


async def to_triggered_event(event_occurrence: EventOccurrenceORM) -> TriggeredEvent:
    """
    Convert an active ORM EventOccurrence object to a game TriggeredEvent object.

    Parameters
    ----------
    event_occurrence: EventOccurrence
        The active event occurrence to convert.

    Returns
    -------
    TriggeredEvent
        The converted triggered event model.
    """

    event = await get_owner_event_by_id(event_occurrence.event_id)
    if event is None:
        raise ValueError(f"Event {event_occurrence.event_id} could not be loaded.")

    context = EventContext.from_dict(event_occurrence.context or {})
    result = EventResult.from_dict(event_occurrence.result_summary or {}) if event_occurrence.result_summary else None
    entity_references = await resolve_event_entity_references(context, result)

    options = []
    if event.requires_response:
        options = [
            await to_event_option(option)
            for option in sorted(event.options, key=lambda option: option.option_order)
            if option.is_visible
        ]

    return TriggeredEvent(
        active_owner_event_id=event_occurrence.id,
        event_id=event.id,
        name=event.name,
        category=event.category,
        description=event.description,
        flavor_text=event.flavor_text,
        severity=event.severity,
        requires_response=event.requires_response,
        response_timeout=event.response_timeout,
        expires_at=event_occurrence.expires_at,
        context=context,
        options=options,
        result=result,
        entity_references=entity_references,
    )
