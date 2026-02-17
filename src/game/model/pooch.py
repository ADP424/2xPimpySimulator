from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from database import get_owner_by_discord_id, get_vendor_by_id, get_pooch_health
from database.models import Pooch as PoochORM

from .owner import Owner, to_owner
from .vendor import Vendor, to_vendor


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
    vendor_id: Optional[int]
    created_at: Optional[datetime]

    health: int

    owner: Optional[Owner]
    vendor: Optional[Vendor]

    @property
    def birthday(self) -> Optional[datetime]:
        return self.created_at

    @property
    def status(self) -> str:
        if not self.alive:
            return "dead"
        elif self.age >= 12:
            return "old"
        elif self.health <= 3:
            return "sick"
        return "healthy"


async def to_pooch(pooch: PoochORM) -> Pooch:
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
        health=(await get_pooch_health(pooch.id)),
        owner_discord_id=pooch.owner_discord_id,
        vendor_id=pooch.vendor_id,
        created_at=pooch.created_at,
        owner=(
            (await to_owner(await get_owner_by_discord_id(pooch.owner_discord_id)))
            if pooch.owner_discord_id is not None
            else None
        ),
        vendor=(await to_vendor(await get_vendor_by_id(pooch.vendor_id))) if pooch.vendor_id is not None else None,
    )
