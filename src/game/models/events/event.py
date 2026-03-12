from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import Event as EventORM


@dataclass(frozen=True)
class Event:
    id: int

    name: str
    category: str
    description: str
    flavor_text: str

    severity: str
    rarity: str

    requires_response: bool
    response_timeout: int
    triggered_only: bool


async def to_event(event: EventORM) -> Event:
    """
    Convert an ORM Event object to a game Event object.

    Parameters
    ----------
    event: Event
        The Event object to convert.

    Returns
    -------
    Event
        The converted Event dataclass object.
    """

    return Event(
        id=event.id,
        name=event.name,
        category=event.category,
        description=event.description,
        flavor_text=event.flavor_text,
        severity=event.severity,
        rarity=event.rarity,
        requires_response=event.requires_response,
        response_timeout=event.response_timeout,
        triggered_only=event.triggered_only,
    )
