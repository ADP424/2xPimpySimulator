from __future__ import annotations

from typing import TYPE_CHECKING

from src.database import add_pooch_to_kennel as db_add_pooch_to_kennel
from src.database import (
    create_kennel,
    get_kennel_by_id,
    get_owner_by_discord_id,
    get_pooch_by_id,
    give_money_to_owner,
    list_kennels_for_owner,
    list_pooches_for_kennel,
    modify_kennel_pooch_limit,
)
from src.database import rename_kennel as db_rename_kennel

from .constants import (
    KENNEL_BASE_PRICE,
    KENNEL_MAX_POOCH_LIMIT,
    KENNEL_UPGRADE_CAPACITY_PER_UPGRADE,
    KENNEL_UPGRADE_PRICE_PER_5,
    MAX_KENNELS,
    MAX_NAME_LENGTH,
)
from .exceptions import KennelNotFound, PoochNotFound
from .models import to_kennel, to_pooch

if TYPE_CHECKING:
    from .models import Pooch


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

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        raise PoochNotFound(pooch_id)

    kennel_pooches = await list_kennel_pooches(kennel_id)
    if len(kennel_pooches) >= kennel.pooch_limit:
        return False

    await db_add_pooch_to_kennel(kennel_id, pooch_id)
    return True


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
    return [(await to_pooch(pooch)) for pooch in pooches]


async def rename_kennel(kennel_id: int, name: str) -> bool:
    """
    Rename the kennel with a given ID.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to rename.

    name: str
        The new name to give the kennel.

    Returns
    -------
    bool
        True if renamed, False if the name is too long.

    Raises
    ------
    KennelNotFound
        When the kennel with the given ID isn't found in the database.
    """

    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        return False

    kennel = await db_rename_kennel(kennel_id, name)
    if kennel is None:
        raise KennelNotFound(kennel_id)
    return True


async def get_kennel_buy_price(owner_discord_id: int) -> tuple[int | None, str]:
    """
    Return the cost to buy the next kennel, or None if the owner is at the limit.

    Returns
    -------
    tuple[int | None, str]
        (price_or_None, status_message)
    """

    kennels = await list_kennels_for_owner(owner_discord_id)
    kennel_count = len(kennels)

    if kennel_count >= MAX_KENNELS:
        return None, f"Maximum kennels owned ({kennel_count}/{MAX_KENNELS})"

    price = max(KENNEL_BASE_PRICE, KENNEL_BASE_PRICE * kennel_count)
    return price, f"Kennel #{kennel_count + 1} — ${price} ({kennel_count}/{MAX_KENNELS} owned)"


async def get_kennel_upgrade_price(kennel_id: int) -> tuple[int | None, str]:
    """
    Return the cost to upgrade the given kennel, or None if already at max.

    Returns
    -------
    tuple[int | None, str]
        (price_or_None, status_message)
    """

    kennel = await get_kennel_by_id(kennel_id)

    if kennel is None:
        return None, "Kennel not found"

    if kennel.pooch_limit >= KENNEL_MAX_POOCH_LIMIT:
        return None, f"Max kennel upgrade reached ({KENNEL_MAX_POOCH_LIMIT} pooches)"

    price = max(KENNEL_UPGRADE_PRICE_PER_5, (kennel.pooch_limit - 5) // 5 * KENNEL_UPGRADE_PRICE_PER_5)
    new_capacity = kennel.pooch_limit + KENNEL_UPGRADE_CAPACITY_PER_UPGRADE
    return price, f"Upgrade to {new_capacity} capacity — ${price}"


async def buy_kennel(owner_discord_id: int) -> tuple[bool, str]:
    """
    Purchase a new kennel for the owner.

    Cost = KENNEL_BASE_PRICE * current kennel count.
    Fails if the owner already has MAX_KENNELS kennels or cannot afford it.

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "You need to visit /home first to set up your account."

    kennels = await list_kennels_for_owner(owner_discord_id)
    kennel_count = len(kennels)

    if kennel_count >= MAX_KENNELS:
        return False, f"You already have the maximum number of kennels ({MAX_KENNELS})."

    price = max(KENNEL_BASE_PRICE, KENNEL_BASE_PRICE * kennel_count)
    if owner.dollars < price:
        return False, f"A new kennel costs ${price}, but you only have ${owner.dollars}."

    await give_money_to_owner(owner_discord_id, -price)
    new_kennel = await create_kennel(owner_discord_id)
    kennel = await to_kennel(new_kennel)
    return True, f"You bought a new kennel (**{kennel.name}**) for ${price}."


async def upgrade_kennel(owner_discord_id: int, kennel_id: int) -> tuple[bool, str]:
    """
    Upgrade the capacity of the given kennel by KENNEL_UPGRADE_CAPACITY_PER_UPGRADE.

    Upgrade cost scales with current capacity: $200 per 5 pooches above 5, minimum $200.
    Fails if the kennel is already at max capacity, the owner can't afford it,
    or the kennel doesn't belong to the owner.

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "You need to visit /home first to set up your account."

    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        return False, "That kennel doesn't exist."
    if kennel.owner_discord_id != owner_discord_id:
        return False, "You don't own that kennel."

    if kennel.pooch_limit >= KENNEL_MAX_POOCH_LIMIT:
        return None, f"Max kennel upgrade reached ({KENNEL_MAX_POOCH_LIMIT} pooches)"

    price = max(KENNEL_UPGRADE_PRICE_PER_5, (kennel.pooch_limit - 5) // 5 * KENNEL_UPGRADE_PRICE_PER_5)

    if owner.dollars < price:
        return False, f"This upgrade costs ${price}, but you only have ${owner.dollars}."

    await give_money_to_owner(owner_discord_id, -price)
    await modify_kennel_pooch_limit(kennel_id, KENNEL_UPGRADE_CAPACITY_PER_UPGRADE)

    new_limit = kennel.pooch_limit + KENNEL_UPGRADE_CAPACITY_PER_UPGRADE
    return True, f"**{kennel.name}** upgraded to {new_limit} pooch capacity for ${price}."
