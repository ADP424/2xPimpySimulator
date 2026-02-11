from typing import Optional
from sqlalchemy import select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)
from .pooch_manager import get_pooch_by_id


async def list_kennels_for_owner(owner_discord_id: int) -> list[Kennel]:
    """
    Fetch the list of kennels owned by the owner with the given Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch the kennels for.

    Returns
    -------
    list[Kennel]
        The list of Kennel ORM objects the owner owns.
    """

    async with session_scope() as session:
        owner = (await session.execute(select(Owner).where(Owner.discord_id == owner_discord_id))).scalar_one_or_none()
        if owner is None:
            return []

        query = (
            select(Kennel)
            .where(Kennel.owner_discord_id == owner.discord_id)
            .order_by(Kennel.created_at.asc(), Kennel.id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def get_owner_by_discord_id(owner_discord_id: int) -> Optional[Owner]:
    """
    Fetch an owner by their Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch.

    Returns
    -------
    Owner, optional
        The Owner ORM object, or None if no owner with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def create_owner(owner_discord_id: int) -> Owner:
    """
    Create an owner with the given Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to create.

    Returns
    -------
    Owner
        The Owner ORM object just created.
    """

    async with session_scope() as session:
        owner = Owner(discord_id=owner_discord_id)
        session.add(owner)
        await session.flush()

    return owner


async def give_money_to_owner(owner_discord_id: int, dollars: int) -> Optional[Owner]:
    """
    Add an amount of money to the given owner's `dollars`.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to give the money to.

    dollars: int
        The number of dollars to give to the owner.

    Returns
    -------
    Owner, optional
        The Owner ORM object the dollars were added to, or None if no owner with the given Discord ID was found.
    """

    owner = await get_owner_by_discord_id(owner_discord_id)

    if owner is None:
        return None

    owner.dollars += dollars
    return owner


async def add_owner_to_server(server_discord_id: int, owner_discord_id: int) -> OwnerServer:
    """
    Add an owner with the given Discord ID to the server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to add the owner to.

    owner_discord_id: int
        The Discord ID of the owner to add to the server.

    Returns
    -------
    OwnerServer, optional
        The OwnerServer relationship ORM object just created.
    """

    async with session_scope() as session:
        owner_server = OwnerServer(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id)
        session.add(owner_server)
        await session.flush()

    return owner_server


async def bury_pooch(owner_discord_id: int, pooch_id: int) -> Optional[GraveyardPooch]:
    """
    Move the given pooch to the given owner's graveyard.

    Parameters
    ----------
    owner_discord_id: int
        The ID of the owner whose graveyard the pooch will be added to.

    pooch_id: int
        The ID of the pooch to bury.

    Returns
    -------
    GraveyardPooch, optional
        The GraveyardPooch ORM object that was just created, or None if the pooch or owner wasn't found.
    """

    owner = await get_owner_by_discord_id(owner_discord_id)
    pooch = await get_pooch_by_id(pooch_id)

    if owner is None or pooch is None:
        return None

    async with session_scope() as session:
        graveyard_pooch = GraveyardPooch(owner_discord_id=owner.discord_id, pooch_id=pooch.id)
        session.add(graveyard_pooch)
        session.flush()

    return graveyard_pooch
