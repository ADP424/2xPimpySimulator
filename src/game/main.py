from database.main import (
    get_owner_by_discord_id,
    create_owner,
    list_kennels_for_owner,
    list_pooches_for_kennel,
    get_pooch_by_id as db_get_pooch_by_id,
    get_pooch_family as db_get_pooch_family,
)

from .model.kennel import Kennel, to_kennel
from .model.owner import Owner, to_owner
from .model.pooch import Pooch, to_pooch


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


async def get_pooch_by_id(server_id: int, pooch_id: int) -> Pooch:
    pooch = await db_get_pooch_by_id(server_id, pooch_id)
    if pooch is None:
        raise KeyError(f"Pooch {pooch_id} not found")
    return to_pooch(pooch)


async def get_pooch_family(server_id: int, pooch_id: int) -> dict[str, list[Pooch]]:
    fam = await db_get_pooch_family(server_id, pooch_id) or {}
    return {
        "parents": [to_pooch(p) for p in fam.get("parents", [])],
        "children": [to_pooch(c) for c in fam.get("children", [])],
        "siblings": [to_pooch(s) for s in fam.get("siblings", [])],
    }
