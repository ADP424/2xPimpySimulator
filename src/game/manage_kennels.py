from database import (
    get_kennel_by_id,
    get_pooch_by_id,
    list_pooches_for_kennel,
    add_pooch_to_kennel as db_add_pooch_to_kennel,
)
from .exceptions.kennel_not_found import KennelNotFound
from .exceptions.pooch_not_found import PoochNotFound

from .model import Pooch, to_pooch


async def list_kennel_pooches(kennel_id: int) -> list[Pooch]:
    """
    List every pooch in a given kennel.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to fetch the pooches from.

    Returns
    -------
    list[Pooch]
        The list of every pooch in the given kennel.

    Raises
    ------
    KennelNotFound
        When the kennel with the given ID isn't found in the database.
    """

    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        raise KennelNotFound(kennel_id)

    pooches = await list_pooches_for_kennel(kennel_id)
    return [to_pooch(pooch) for pooch in pooches]


async def add_pooch_to_kennel(kennel_id: int, pooch_id: int) -> bool:
    """
    Add the pooch with the given ID to the kennel with the given ID.
    Adding fails if the kennel is out of space.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to add the pooch to.

    pooch_id: int
        The ID of the pooch to add to the kennel.

    Returns
    -------
    bool
        Whether the pooch was added successfully or not.

    Raises
    ------
    KennelNotFound
        When the kennel with the given ID isn't found in the database.

    PoochNotFound
        When the pooch with the given ID isn't found in the database.
    """

    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        raise KennelNotFound(kennel_id)

    pooch = await get_pooch_by_id(kennel_id)
    if pooch is None:
        raise PoochNotFound(pooch_id)

    kennel_pooches = await list_kennel_pooches(kennel_id)
    if len(kennel_pooches) >= kennel.pooch_limit:
        return False

    await db_add_pooch_to_kennel(kennel_id, pooch_id)
