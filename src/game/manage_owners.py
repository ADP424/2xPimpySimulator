from database import (
    get_owner_by_discord_id,
    create_owner,
    create_kennel,
    add_owner_to_server,
    list_kennels_for_owner,
    list_pooches_for_kennel,
    give_money_to_owner,
)

from .model import Kennel, to_kennel, Owner, to_owner, Pooch, to_pooch


async def get_or_create_owner(server_id: int, owner_discord_id: int) -> Owner:
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        owner = await create_owner(owner_discord_id)
        await add_owner_to_server(server_id, owner_discord_id)
        await create_kennel(owner_discord_id)

    return to_owner(owner)


async def list_owner_kennels(server_id: int, owner_discord_id: int) -> list[Kennel]:
    kennels = await list_kennels_for_owner(owner_discord_id)
    return [to_kennel(k) for k in kennels]


async def list_kennel_pooches(server_id: int, kennel_id: int) -> list[Pooch]:
    pooches = await list_pooches_for_kennel(kennel_id)
    return [to_pooch(p) for p in pooches]


async def add_money(server_id: int, owner_discord_id: int, amount: int) -> Owner:
    owner = await give_money_to_owner(owner_discord_id, amount)
    if owner is None:
        await get_or_create_owner(server_id, owner_discord_id)
        owner = await give_money_to_owner(owner_discord_id, amount)
        if owner is None:
            raise RuntimeError("Failed to create owner")
    return to_owner(owner)
