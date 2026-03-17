from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_pooch_parents,
    list_pooch_children,
    list_pooch_siblings,
)
from src.database import rename_pooch as db_rename_pooch
from src.database import (
    tick_hourly_breeding_cooldowns,
)
from src.logger import get_logger

from .constants import BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR, MAX_NAME_LENGTH
from .exceptions import PoochNotFound
from .models import to_pooch

logger = get_logger("game/manage_pooches")

if TYPE_CHECKING:
    from .models import Pooch


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
    PoochNotFound
        When a Pooch with `pooch_id` is not found.
    """

    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        raise PoochNotFound(f"Pooch {pooch_id} not found.")
    return await to_pooch(pooch)


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
    parents = [(await to_pooch(parent)) for parent in (father, mother) if parent is not None]

    children_orm = await list_pooch_children(pooch_id)
    children = [(await to_pooch(child)) for child in children_orm]

    siblings_orm = await list_pooch_siblings(pooch_id)
    siblings = [(await to_pooch(sibling)) for sibling in siblings_orm]

    return {
        "parents": parents,
        "children": children,
        "siblings": siblings,
    }


async def run_hourly_breeding_cooldown_check(rng_seed: Optional[int] = None) -> int:
    """
    Roll a fertility-based chance to decrement each living pooch's breeding cooldown by 1.

    Chance per pooch = fertility / BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR.

    Parameters
    ----------
    rng_seed: int, optional
        Seed for reproducible rolls.

    Returns
    -------
    int
        Number of pooches whose cooldown was decremented.
    """

    decremented = await tick_hourly_breeding_cooldowns(
        fertility_divisor=BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR,
        rng_seed=rng_seed,
    )
    logger.info("Hourly breeding cooldown tick: %d pooch(es) decremented.", decremented)
    return decremented


async def rename_pooch(pooch_id: int, name: str) -> bool:
    """
    Rename the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to rename.

    name: str
        The new name to give the pooch.

    max_name_length: int
        Maximum allowed name length.

    Returns
    -------
    bool
        True if renamed, False if the name is too long.

    Raises
    ------
    PoochNotFound
        When a Pooch with `pooch_id` is not found.
    """

    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        return False

    pooch = await db_rename_pooch(pooch_id, name)
    if pooch is None:
        raise PoochNotFound(pooch_id)
    return True
