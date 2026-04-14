from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.models.pooch import Pooch
    from src.game.models.server import Server

    from .birth_event import BirthEvent
    from .death_event import DeathEvent
    from .other_event import OtherEvent


@dataclass(frozen=True)
class HourChangeSummary:
    """Per-server summary of a single hour tick.

    Uses the same per-event dataclasses as ``DayChangeSummary``. The hour
    summary is only posted to the server event channel when at least one
    of the lists is non-empty, so quiet hours don't spam the feed.
    """

    server: Server
    hour: int
    births: list[BirthEvent] = field(default_factory=list)
    deaths: list[DeathEvent] = field(default_factory=list)
    other_events: list[OtherEvent] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.births or self.deaths or self.other_events)

    @property
    def dead_pooches(self) -> list[Pooch]:
        seen: set[int] = set()
        out: list[Pooch] = []
        for death in self.deaths:
            if death.pooch.id not in seen:
                seen.add(death.pooch.id)
                out.append(death.pooch)
        return out

    @property
    def birthed_pooches(self) -> list[Pooch]:
        seen: set[int] = set()
        out: list[Pooch] = []
        for birth in self.births:
            if birth.child.id not in seen:
                seen.add(birth.child.id)
                out.append(birth.child)
        return out

    @property
    def other_pooches(self) -> list[Pooch]:
        seen: set[int] = set()
        out: list[Pooch] = []
        for event in self.other_events:
            if event.pooch.id not in seen:
                seen.add(event.pooch.id)
                out.append(event.pooch)
        return out
