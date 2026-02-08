from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from database.models import Owner as PoochORM


@dataclass(frozen=True)
class Pooch:
    id: int
    server_id: int
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
        id=int(getattr(pooch, "id")),
        server_id=int(getattr(pooch, "server_id")),
        name=str(getattr(pooch, "name")),
        age=int(getattr(pooch, "age", -1)),
        sex=str(getattr(pooch, "sex", "Unknown")),
        base_health=int(getattr(pooch, "base_health", 10)),
        health_loss_age=int(getattr(pooch, "health_loss_age", 0)),
        alive=bool(getattr(pooch, "alive", True)),
        owner_discord_id=getattr(pooch, "owner_discord_id", None),
        created_at=getattr(pooch, "created_at", None),
    )
