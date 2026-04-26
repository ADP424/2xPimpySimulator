from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import Owner as OwnerORM


@dataclass(frozen=True)
class Owner:
    discord_id: int
    discord_name: str | None
    dollars: int
    bloodskulls: int
    bones: int
    begged_today: bool = False
    visited_park_today: bool = False


async def to_owner(owner: OwnerORM) -> Owner:
    """
    Convert an ORM Owner object to a game Owner object.

    Parameters
    ----------
    owner: Owner
        The Owner object to convert.

    Returns
    -------
    Owner
        The converted Owner dataclass object.
    """

    return Owner(
        discord_id=owner.discord_id,
        discord_name=owner.discord_name,
        dollars=owner.dollars,
        bloodskulls=owner.bloodskulls,
        bones=owner.bones,
        begged_today=owner.begged_today,
        visited_park_today=owner.visited_park_today,
    )
