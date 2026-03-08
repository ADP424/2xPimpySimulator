from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from database import list_graveyard_pooches_for_owner

from .models import to_pooch

if TYPE_CHECKING:
    from .models import Pooch


async def list_graveyard_pooches(owner_discord_id: int) -> list[tuple[Pooch, datetime]]:
    """
    List every deceased pooch buried by the given owner, most recently buried first.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch the buried pooches for.

    Returns
    -------
    list[tuple[Pooch, datetime]]
        A list of (game Pooch, buried_at datetime) tuples.
    """

    rows = await list_graveyard_pooches_for_owner(owner_discord_id)
    return [(await to_pooch(pooch), buried_at) for pooch, buried_at in rows]
