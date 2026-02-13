from database import (
    get_owner_by_discord_id,
    create_owner,
    create_kennel,
    add_owner_to_server,
    list_kennels_for_owner,
    give_money_to_owner,
    get_owner_server,
)
from .manage_servers import get_or_create_server
from .exceptions.owner_not_found import OwnerNotFound

from .model import Kennel, to_kennel, Owner, to_owner


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

    await get_or_create_server(server_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        owner = await create_owner(owner_discord_id)
        await add_owner_to_server(server_discord_id, owner_discord_id)
        await create_kennel(owner_discord_id)
    else:
        owner_server = await get_owner_server(server_discord_id, owner_discord_id)
        if owner_server is None:
            await add_owner_to_server(server_discord_id, owner_discord_id)

    return to_owner(owner)


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
    return [to_kennel(kennel) for kennel in kennels]


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
    return to_owner(owner)
