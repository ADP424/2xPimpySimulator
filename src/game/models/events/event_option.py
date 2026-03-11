from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models import EventOption as EventOptionORM


@dataclass(frozen=True)
class EventOption:
    id: int
    label: str
    description: str
    min_money: int
    min_bloodskulls: int
    is_default: bool
    is_visible: bool


async def to_event_option(option: EventOptionORM) -> EventOption:
    """
    Convert an ORM EventOption object to a game EventOption object.

    Parameters
    ----------
    option: EventOption
        The EventOption ORM object to convert.

    Returns
    -------
    EventOption
        The converted game EventOption object.
    """

    return EventOption(
        id=option.id,
        label=option.label,
        description=option.description,
        min_money=option.min_money,
        min_bloodskulls=option.min_bloodskulls,
        is_default=option.is_default,
        is_visible=option.is_visible,
    )
