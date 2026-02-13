from typing import Optional
from sqlalchemy import select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)


async def get_pooch_by_id(pooch_id: int) -> Optional[Pooch]:
    """
    Fetch the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch.

    Returns
    -------
    Option[Pooch]
        The Pooch ORM object with the given ID, or None if no Pooch with that ID exists.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


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


async def get_kennel_by_id(kennel_id: int) -> Optional[Kennel]:
    """
    Fetch the kennel with the given ID.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to fetch.

    Returns
    -------
    Kennel, optional
        The Kennel ORM object with the given ID, or None if no kennel with the given ID was found.
    """

    async with session_scope() as session:
        response = await session.execute(select(Kennel).where(Kennel.id == kennel_id))

    return response.scalar_one_or_none()


async def get_vendor_by_id(vendor_id: int) -> Optional[Vendor]:
    """
    Fetch the vendor with the given ID.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to fetch.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object with the given ID, or None if no vendor with that ID was found.
    """

    async with session_scope() as session:
        response = await session.execute(select(Vendor).where(Vendor.id == vendor_id))

    vendor = response.scalar_one_or_none()
    return vendor


async def get_server_by_discord_id(server_discord_id: int) -> Optional[Server]:
    """
    Fetch a server by its Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The ID of the server to fetch.

    Returns
    -------
    Server, optional
        The Server ORM object, or None if no server with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Server).where(Server.discord_id == server_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_pooch_kennel(pooch_id: int) -> Optional[Kennel]:
    """
    Fetch the kennel the pooch with the given ID belongs to.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch the kennel of.

    Returns
    -------
    Kennel, optional
        The Kennel the pooch with the given ID belongs to, or None if it doesn't belong to a kennel.
    """

    async with session_scope() as session:
        query = (
            select(Kennel)
            .join(KennelPooch, KennelPooch.kennel_id == Kennel.id)
            .join(Owner, Owner.discord_id == Kennel.owner_discord_id)
            .where(KennelPooch.pooch_id == pooch_id)
            .limit(1)
        )
        response = await session.execute(query)

    kennel = response.scalar_one_or_none()
    return kennel


async def get_pooch_parents(pooch_id: int) -> tuple[Optional[Pooch], Optional[Pooch]]:
    """
    Fetch the parents of the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch the parents of.

    Returns
    -------
    tuple[Optional[Pooch], Optional[Pooch]]
        A tuple of Pooch ORM objects in the form (father, mother).
    """

    async with session_scope() as session:
        parentage = (
            await session.execute(select(PoochParentage).where(PoochParentage.child_id == pooch_id))
        ).scalar_one_or_none()

    if not parentage:
        return (None, None)

    father = await get_pooch_by_id(parentage.father_id)
    mother = await get_pooch_by_id(parentage.mother_id)

    return (father, mother)


async def get_vendor_server(vendor_id: int) -> Optional[Server]:
    """
    Get the server the vendor with the given ID belongs to.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to get the server for.

    Returns
    -------
    Server, optional
        The Server ORM object representing the server the vendor belongs to.
    """

    async with session_scope() as session:
        query = select(Server).join(Vendor, Vendor.server_discord_id == Server.discord_id).where(Vendor.id == vendor_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_server(server_discord_id: int, owner_discord_id: int) -> Optional[OwnerServer]:
    """
    Get the owner-server relationship with the given server and owner Discord IDs.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server in the owner-server relationship.

    owner_discord_id: int
        The Discord ID of the owner in the owner-server relationship.

    Returns
    -------
    OwnerServer, optional
        The OwnerServer ORM relationship object with the given ID pair, or None if it doesn't exist.
    """

    async with session_scope() as session:
        query = select(OwnerServer).where(
            OwnerServer.server_discord_id == server_discord_id and OwnerServer.owner_discord_id == owner_discord_id
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()
