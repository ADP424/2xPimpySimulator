from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models.event_types import (
        TriggeredEventEntityReference,
        TriggeredEventOptionDict,
    )

    from .event_context import EventContext
    from .event_result import EventResult


@dataclass
class TriggeredEvent:
    active_event_id: int
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
    options: list[TriggeredEventOptionDict] = field(default_factory=list)
    result: EventResult | None = None
    entity_references: dict[str, list[TriggeredEventEntityReference]] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
