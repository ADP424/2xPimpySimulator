from database import list_hell_pooches as db_list_hell_pooches

from .models import Pooch, to_pooch


async def list_hell_pooches() -> list[Pooch]:
    """
    List every pooch in the global Hell, most recently damned first.

    Returns
    -------
    list[Pooch]
        A list of Pooch objects representing those sacrificed to Hell.
    """

    rows = await db_list_hell_pooches()
    return [to_pooch(pooch) for pooch in rows]


async def get_pooch_bloodskull_value(pooch_id: int) -> int:
    """
    Get the total price to buy the given pooch from the given vendor.
    If no vendor is provided, the returned price is the pooch's base price.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the price of.

    vendor_id: int, optional
        The ID of the vendor to check for the value they put on the pooch they're selling.

    Returns
    -------
    int
        The value of the pooch in dollars, optionally augmented by the given vendor.
    """
