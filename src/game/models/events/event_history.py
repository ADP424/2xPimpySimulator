from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from database import get_owner_event_by_id, get_owner_event_option_by_id

from .event_context import EventContext
from .event_entity_reference import (
    EventEntityReferences,
    resolve_event_entity_references,
)
from .event_option import EventOption, to_event_option
from .event_result import EventResult

if TYPE_CHECKING:
    from database.models import EventOccurrence as EventOccurrenceORM


@dataclass
class EventHistory:
    id: int
    event_id: int

    name: str = "Unknown Event"
    description: str | None = None
    category: str = "unknown"
    severity: str = "moderate"
    flavor_text: str | None = None

    context: EventContext = field(default_factory=lambda: EventContext(owner_discord_id=0))
    entity_references: EventEntityReferences = field(default_factory=EventEntityReferences)
    result_summary: EventResult = field(default_factory=EventResult)

    triggered_at: datetime | None = None
    completed_at: datetime | None = None

    selected_option: EventOption | None = None
    timed_out: bool = False

    @property
    def selected_option_id(self) -> int | None:
        return self.selected_option.id if self.selected_option is not None else None

    @property
    def selected_option_label(self) -> str | None:
        return self.selected_option.label if self.selected_option is not None else None


async def to_event_history(event_occurrence: EventOccurrenceORM) -> EventHistory:
    """
    Convert an ORM EventOccurrence object to a game EventHistory object.

    Parameters
    ----------
    event_occurrence: EventOccurrence
        The database EventOccurrence object to convert.

    Returns
    -------
    EventHistory
        A look into this historical EventOccurrence.
    """

    event = await get_owner_event_by_id(event_occurrence.event_id)

    selected_option_orm = event_occurrence.selected_option
    if selected_option_orm is None and event_occurrence.selected_option_id is not None:
        selected_option_orm = await get_owner_event_option_by_id(event_occurrence.selected_option_id)

    context = EventContext.from_dict(event_occurrence.context or {})
    result_summary = EventResult.from_dict(event_occurrence.result_summary or {})
    entity_references = await resolve_event_entity_references(context, result_summary)

    return EventHistory(
        id=event_occurrence.id,
        event_id=event_occurrence.event_id,
        name=event.name if event is not None else "Unknown Event",
        description=event.description if event is not None else None,
        category=event.category if event is not None else "unknown",
        severity=event.severity if event is not None else "moderate",
        flavor_text=event.flavor_text if event is not None else None,
        context=context,
        entity_references=entity_references,
        result_summary=result_summary,
        triggered_at=event_occurrence.triggered_at,
        completed_at=event_occurrence.completed_at,
        selected_option=(await to_event_option(selected_option_orm)) if selected_option_orm is not None else None,
        timed_out=event_occurrence.timed_out,
    )
