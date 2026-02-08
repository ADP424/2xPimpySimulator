from dataclasses import dataclass

from .birth_event import BirthEvent
from .death_event import DeathEvent


@dataclass(frozen=True)
class DayChangeSummary:
    server_id: int
    births: list[BirthEvent]
    deaths: list[DeathEvent]

    @property
    def mentioned_pooch_ids(self) -> list[int]:
        ids: list[int] = []

        for birth in self.births:
            ids.extend([birth.mother_id, birth.child_id])
        for death in self.deaths:
            ids.append(death.pooch_id)

        seen = set()
        out: list[int] = []
        for id in ids:
            if id not in seen:
                seen.add(id)
                out.append(id)

        return out
