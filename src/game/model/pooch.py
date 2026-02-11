from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from database.models import Pooch as PoochORM


@dataclass(frozen=True)
class Pooch:
    id: int
    name: str
    age: int
    sex: str

    base_health: int
    health_loss_age: int
    alive: bool
    owner_discord_id: Optional[int]
    created_at: Optional[datetime]

    @property
    def birthday(self) -> Optional[datetime]:
        return self.created_at

    @property
    def health(self) -> int:
        return max(int(self.base_health) - int(self.health_loss_age), 0)

    @property
    def status(self) -> str:
        if not self.alive:
            return "dead"
        elif self.health <= 3:
            return "unhealthy"
        elif self.age >= 12:
            return "old"
        return "healthy"


def to_pooch(pooch: PoochORM) -> Pooch:
    """
    Convert an ORM Pooch object to a game Pooch object.

    Parameters
    ----------
    pooch: Pooch
        The Pooch object to convert.

    Returns
    -------
    Pooch
        The converted Pooch dataclass object.
    """

    return Pooch(
        id=pooch.id,
        name=pooch.name,
        age=pooch.age,
        sex=pooch.sex,
        base_health=pooch.base_health,
        health_loss_age=pooch.health_loss_age,
        alive=pooch.alive,
        owner_discord_id=pooch.owner_discord_id,
        created_at=pooch.created_at,
    )
