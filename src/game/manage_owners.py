import random
from typing import Optional

from database import (
    add_breed_to_pooch,
    add_owner_to_server,
    add_pooch_to_kennel,
    create_kennel,
    create_owner,
    create_pooch,
    get_owner_by_discord_id,
    get_owner_server,
    give_money_to_owner,
    list_kennels_for_owner,
    set_owner_begged_today,
)

from .constants import BEG_DOLLARS_RANGE, BEG_MAX_DOLLARS
from .exceptions.owner_not_found import OwnerNotFound
from .manage_servers import get_or_create_server
from .models import Kennel, Owner, to_kennel, to_owner


async def add_money(server_discord_id: int, owner_discord_id: int, amount: int) -> Owner:
    """
    Add money to the owner with the given ID's account.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server the owner is getting the money on.

    owner_discord_id: int
        The Discord ID of the owner to give the money.

    Returns
    -------
    Owner
        The Owner with the given Discord ID that received the money.
    """

    owner = await give_money_to_owner(owner_discord_id, amount)
    if owner is None:
        await get_or_create_owner(server_discord_id, owner_discord_id)
        owner = await give_money_to_owner(owner_discord_id, amount)
        if owner is None:
            raise OwnerNotFound(owner_discord_id)
    return await to_owner(owner)


async def beg_for_money(
    server_discord_id: int, owner_discord_id: int, rng: random.Random | None = None
) -> tuple[int, Optional[str]]:
    """
    Beg for money at the church.

    An owner may only beg once per day, and only if they have `BEG_MAX_DOLLARS` or fewer dollars.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server the owner is begging in.

    owner_discord_id: int
        The Discord ID of the owner begging.

    rng: Random, optional
        The random generator to use to determine the amount.

    Returns
    -------
    tuple[int, str, optional]
        The a tuple in the form (amount of money received, failure message or None if success).
    """

    rng = rng if rng is not None else random.Random()

    await get_or_create_owner(server_discord_id, owner_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        raise OwnerNotFound(owner_discord_id)

    if owner.dollars > BEG_MAX_DOLLARS:
        return 0, "You have too much money to beg. Shame!"
    if owner.begged_today:
        return 0, "You already begged today, friend."

    amount = rng.randint(BEG_DOLLARS_RANGE[0], BEG_DOLLARS_RANGE[1])
    await give_money_to_owner(owner_discord_id, amount)
    await set_owner_begged_today(owner_discord_id)

    return amount, None


async def get_or_create_owner(server_discord_id: int, owner_discord_id: int) -> Owner:
    """
    Get an owner with the given Discord ID for the server with the given Discord ID.
    If no owner with that ID exists on that server yet, create it.
    Also creates the server if it doesn't exist yet.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to get the owner from / add the owner to.

    owner_discord_id: int
        The Discord ID of the owner to get / create / add to the server.

    Returns
    -------
    Owner
        The Owner with the given Discord ID in the server with the given Discord ID.
    """

    async def _create_owner_starting_objects(owner_discord_id: int):
        """Add the owner to the sever and give them their starting items."""

        await add_owner_to_server(server_discord_id, owner_discord_id)
        kennel = await create_kennel(owner_discord_id)
        # TODO pass random
        female_pooch = await create_pooch(owner_discord_id=owner_discord_id, sex="female", age=1, breeding_cooldown=0)
        male_pooch = await create_pooch(owner_discord_id=owner_discord_id, sex="male", age=1, breeding_cooldown=0)
        await add_breed_to_pooch(female_pooch.id, from_vendor=True)
        await add_breed_to_pooch(male_pooch.id, from_vendor=True)
        await add_pooch_to_kennel(kennel.id, female_pooch.id)
        await add_pooch_to_kennel(kennel.id, male_pooch.id)

    await get_or_create_server(server_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        owner = await create_owner(owner_discord_id)
        await _create_owner_starting_objects(owner.discord_id)
    else:
        owner_server = await get_owner_server(server_discord_id, owner_discord_id)
        if owner_server is None:
            await add_owner_to_server(server_discord_id, owner_discord_id)

    return await to_owner(owner)


async def list_owner_kennels(owner_discord_id: int) -> list[Kennel]:
    """
    Get a list of every kennel the owner with the given Discord ID owns.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to get the kennels for.

    Returns
    -------
    list[Kennel]
        The list of kennels the owner with the given Discord ID owns.
    """

    kennels = await list_kennels_for_owner(owner_discord_id)
    return [(await to_kennel(kennel)) for kennel in kennels]
