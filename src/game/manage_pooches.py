from database import (
    get_pooch_by_id as db_get_pooch_by_id,
    get_pooch_parents,
    list_pooch_children,
    list_pooch_siblings,
)

from .model import Pooch, to_pooch


async def get_pooch_by_id(server_id: int, pooch_id: int) -> Pooch:
    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        raise KeyError(f"Pooch {pooch_id} not found")
    return to_pooch(pooch)


async def get_pooch_family(server_id: int, pooch_id: int) -> dict[str, list[Pooch]]:
    father, mother = await get_pooch_parents(pooch_id)
    parents = [to_pooch(p) for p in (father, mother) if p is not None]

    children_orm = await list_pooch_children(pooch_id)
    children = [to_pooch(c) for c in children_orm]

    siblings_orm = await list_pooch_siblings(pooch_id)
    siblings = [to_pooch(s) for s in siblings_orm]

    return {
        "parents": parents,
        "children": children,
        "siblings": siblings,
    }
