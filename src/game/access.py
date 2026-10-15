from __future__ import annotations

from typing import Optional

from src.database import get_kennel_by_id, get_pooch_by_id


async def owns_pooch(owner_discord_id: int, pooch_id: int) -> Optional[bool]:
    """
    Check whether an owner owns a pooch.

    Returns
    -------
    bool, optional
        None if no pooch has that ID, otherwise whether ``owner_discord_id`` owns it.
    """

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return None
    return pooch.owner_discord_id == owner_discord_id


async def owns_kennel(owner_discord_id: int, kennel_id: int) -> Optional[bool]:
    """
    Check whether an owner owns a kennel.

    Returns
    -------
    bool, optional
        None if no kennel has that ID, otherwise whether ``owner_discord_id`` owns it.
    """

    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        return None
    return kennel.owner_discord_id == owner_discord_id
