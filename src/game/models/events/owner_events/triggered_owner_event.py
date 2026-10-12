from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.database import get_owner_event_by_id

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
class TriggeredOwnerEvent:
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

    context: OwnerEventContext
    options: list[OwnerEventOption] = field(default_factory=list)
    result: OwnerEventResult | None = None
    entity_references: OwnerEventEntityReferences = field(default_factory=OwnerEventEntityReferences)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def featured_pooch_id(self) -> int | None:
        """The first pooch in the slot the event features, if it names one."""
        extra = self.context.extra_data
        slot_name = extra.get("_featured_pooch_slot")
        if not isinstance(slot_name, str) or not slot_name:
            return None
        slot = extra.get(slot_name, {})
        pooch_ids = slot.get("pooch_ids", []) if isinstance(slot, dict) else []
        return pooch_ids[0] if pooch_ids else None


async def to_triggered_owner_event(event_occurrence: EventOccurrenceORM) -> TriggeredOwnerEvent:
    """
    Convert an active ORM EventOccurrence object to a game TriggeredOwnerEvent object.

    Parameters
    ----------
    event_occurrence: EventOccurrence
        The active event occurrence to convert.

    Returns
    -------
    TriggeredOwnerEvent
        The converted triggered owner event model.
    """

    event = await get_owner_event_by_id(event_occurrence.event_id)
    if event is None:
        raise ValueError(f"Event {event_occurrence.event_id} could not be loaded.")

    context = OwnerEventContext.from_dict(event_occurrence.context or {})
    result = (
        OwnerEventResult.from_dict(event_occurrence.result_summary or {}) if event_occurrence.result_summary else None
    )
    entity_references = await resolve_owner_event_entity_references(context, result)

    options = []
    if event.requires_response:
        suppressed_option_ids: set[int] = set(
            context.extra_data.get("suppressed_option_ids", [])
            if isinstance(context.extra_data.get("suppressed_option_ids"), list)
            else []
        )
        options = [
            await to_owner_event_option(option)
            for option in sorted(event.options, key=lambda option: option.option_order)
            if option.is_visible and option.id not in suppressed_option_ids
        ]

    return TriggeredOwnerEvent(
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
