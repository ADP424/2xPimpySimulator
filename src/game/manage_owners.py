from database import (
    get_owner_by_discord_id,
    create_owner,
    list_kennels_for_owner,
    list_pooches_for_kennel,
)

from .model import Kennel, to_kennel, Owner, to_owner, Pooch, to_pooch


async def get_or_create_owner(server_id: int, owner_discord_id: int) -> Owner:
    owner = await get_owner_by_discord_id(server_id, owner_discord_id)
    if owner is None:
        owner = await create_owner(server_id, owner_discord_id)
    return to_owner(owner)


async def list_owner_kennels(server_id: int, owner_discord_id: int) -> list[Kennel]:
    kennels = await list_kennels_for_owner(server_id, owner_discord_id)
    return [to_kennel(k) for k in kennels]


async def list_kennel_pooches(server_id: int, kennel_id: int) -> list[Pooch]:
    pooches = await list_pooches_for_kennel(server_id, kennel_id)
    return [to_pooch(p) for p in pooches]
