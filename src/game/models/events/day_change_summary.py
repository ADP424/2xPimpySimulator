from dataclasses import dataclass

from game.models.pooch import Pooch
from game.models.server import Server

from .birth_event import BirthEvent
from .death_event import DeathEvent


@dataclass(frozen=True)
class DayChangeSummary:
    server: Server
    births: list[BirthEvent]
    deaths: list[DeathEvent]

    @property
    def birthed_pooches(self) -> list[Pooch]:
        seen: set[int] = set()
        out: list[Pooch] = []
        for birth in self.births:
            child = birth.child
            if child.id not in seen:
                seen.add(child.id)
                out.append(child)
        return out

    @property
    def dead_pooches(self) -> list[Pooch]:
        seen: set[int] = set()
        out: list[Pooch] = []
        for death in self.deaths:
            pooch = death.pooch
            if pooch.id not in seen:
                seen.add(pooch.id)
                out.append(pooch)
        return out
