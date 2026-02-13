from database import (
    get_pooch_by_id as db_get_pooch_by_id,
    get_pooch_parents,
    list_pooch_children,
    list_pooch_siblings,
)
from .exceptions.pooch_not_found import PoochNotFound

from .model import Pooch, to_pooch


async def get_pooch_by_id(pooch_id: int) -> Pooch:
    """
    Return a pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to return.

    Returns
    -------
    Pooch
        The pooch with the given ID.

    Raises
    ------
    KeyError
        When a Pooch with `pooch_id` is not found.
    """

    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        raise PoochNotFound(f"Pooch {pooch_id} not found.")
    return to_pooch(pooch)


async def get_pooch_family(pooch_id: int) -> dict[str, list[Pooch]]:
    """
    Get the immediate family (parents, children, full siblings) of the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the family of.

    Returns
    -------
    dict[str, list[Pooch]]
        A dictionary in the form `{ "parents": list[Pooch], "children": list[Pooch], "siblings": list[Pooch] }`.
    """

    father, mother = await get_pooch_parents(pooch_id)
    parents = [to_pooch(parent) for parent in (father, mother) if parent is not None]

    children_orm = await list_pooch_children(pooch_id)
    children = [to_pooch(child) for child in children_orm]

    siblings_orm = await list_pooch_siblings(pooch_id)
    siblings = [to_pooch(sibling) for sibling in siblings_orm]

    return {
        "parents": parents,
        "children": children,
        "siblings": siblings,
    }
