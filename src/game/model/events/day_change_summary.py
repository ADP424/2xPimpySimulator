from dataclasses import dataclass

from game.model.pooch import Pooch
from game.model.server import Server

from .birth_event import BirthEvent
from .death_event import DeathEvent


@dataclass(frozen=True)
class DayChangeSummary:
    server: Server
    births: list[BirthEvent]
    deaths: list[DeathEvent]

    @property
    def mentioned_pooches(self) -> list[Pooch]:
        pooches: list[Pooch] = []

        for birth in self.births:
            pooches.extend([birth.mother, birth.child])
        for death in self.deaths:
            pooches.append(death.pooch)

        seen: set[int] = set()
        mentioned: list[Pooch] = []
        for pooch in pooches:
            if pooch.id not in seen:
                seen.add(pooch.id)
                mentioned.append(pooch)

        return mentioned
