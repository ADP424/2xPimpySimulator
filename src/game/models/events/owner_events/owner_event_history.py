from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from src.database import get_owner_event_by_id, get_owner_event_option_by_id

from .owner_event_context import OwnerEventContext
from .owner_event_entity_reference import (
    OwnerEventEntityReferences,
    resolve_owner_event_entity_references,
)
from .owner_event_option import OwnerEventOption, to_owner_event_option
from .owner_event_result import OwnerEventResult

if TYPE_CHECKING:
    from src.database.models import EventOccurrence as EventOccurrenceORM


@dataclass
class OwnerEventHistory:
    id: int
    event_id: int

    name: str = "Unknown Event"
    description: str | None = None
    category: str = "unknown"
    severity: str = "moderate"
    flavor_text: str | None = None

    context: OwnerEventContext = field(default_factory=lambda: OwnerEventContext(owner_discord_id=0))
    entity_references: OwnerEventEntityReferences = field(default_factory=OwnerEventEntityReferences)
    result_summary: OwnerEventResult = field(default_factory=OwnerEventResult)

    triggered_at: datetime | None = None
    completed_at: datetime | None = None

    selected_option: OwnerEventOption | None = None
    timed_out: bool = False

    @property
    def selected_option_id(self) -> int | None:
        return self.selected_option.id if self.selected_option is not None else None

    @property
    def selected_option_label(self) -> str | None:
        return self.selected_option.label if self.selected_option is not None else None


async def to_owner_event_history(event_occurrence: EventOccurrenceORM) -> OwnerEventHistory:
    """
    Convert an ORM EventOccurrence object to a game OwnerEventHistory object.

    Parameters
    ----------
    event_occurrence: EventOccurrence
        The database EventOccurrence object to convert.

    Returns
    -------
    OwnerEventHistory
        A look into this historical EventOccurrence.
    """

    event = await get_owner_event_by_id(event_occurrence.event_id)

    selected_option_orm = event_occurrence.selected_option
    if selected_option_orm is None and event_occurrence.selected_option_id is not None:
        selected_option_orm = await get_owner_event_option_by_id(event_occurrence.selected_option_id)

    context = OwnerEventContext.from_dict(event_occurrence.context or {})
    result_summary = OwnerEventResult.from_dict(event_occurrence.result_summary or {})
    entity_references = await resolve_owner_event_entity_references(context, result_summary)

    return OwnerEventHistory(
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
        selected_option=(await to_owner_event_option(selected_option_orm)) if selected_option_orm is not None else None,
        timed_out=event_occurrence.timed_out,
    )
