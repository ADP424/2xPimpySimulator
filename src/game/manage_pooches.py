from database import (
    get_pooch_by_id as db_get_pooch_by_id,
    get_pooch_family as db_get_pooch_family,
)

from .model import Pooch, to_pooch


async def get_pooch_by_id(server_id: int, pooch_id: int) -> Pooch:
    pooch = await db_get_pooch_by_id(server_id, pooch_id)
    if pooch is None:
        raise KeyError(f"Pooch {pooch_id} not found")
    return to_pooch(pooch)


async def get_pooch_family(server_id: int, pooch_id: int) -> dict[str, list[Pooch]]:
    family = await db_get_pooch_family(server_id, pooch_id) or {}
    return {
        "parents": [to_pooch(p) for p in family.get("parents", [])],
        "children": [to_pooch(c) for c in family.get("children", [])],
        "siblings": [to_pooch(s) for s in family.get("siblings", [])],
    }
