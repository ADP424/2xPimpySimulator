from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from src.database import get_owner_by_discord_id

from .owner import to_owner

if TYPE_CHECKING:
    from src.database.models import Kennel as KennelORM

    from .owner import Owner


@dataclass(frozen=True)
class Kennel:
    id: int
    owner_discord_id: int
    name: str
    pooch_limit: int
    messiness: int = 0
    food_stock: int = 0

    owner: Optional[Owner] = None


async def to_kennel(kennel: KennelORM) -> Kennel:
    """
    Convert an ORM Kennel object to a game Kennel object.

    Parameters
    ----------
    kennel: Kennel
        The Kennel object to convert.

    Returns
    -------
    Kennel
        The converted Kennel dataclass object.
    """

    return Kennel(
        id=kennel.id,
        owner_discord_id=kennel.owner_discord_id,
        name=kennel.name,
        pooch_limit=kennel.pooch_limit,
        messiness=kennel.messiness,
        food_stock=kennel.food_stock,
        owner=(
            (await to_owner(await get_owner_by_discord_id(kennel.owner_discord_id)))
            if kennel.owner_discord_id is not None
            else None
        ),
    )
