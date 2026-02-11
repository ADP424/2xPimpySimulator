from typing import Optional
from sqlalchemy import or_, select

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


async def list_pooches_for_kennel(kennel_id: int) -> list[Pooch]:
    """
    Fetch the list of Pooches in the kennel with the given ID.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to fetch the pooches from.

    Returns
    -------
    list[Pooch]
        The list of Pooch ORM objects in the kennel.
    """

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(KennelPooch, KennelPooch.pooch_id == Pooch.id)
            .where(KennelPooch.kennel_id == kennel_id)
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


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


async def list_living_pooches() -> list[Pooch]:
    """
    Fetch a list of every living pooch.

    Returns
    -------
    list[Pooch]
        The list of every living pooch across all servers.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.alive == True)
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_pooch_children(pooch_id: int) -> list[Pooch]:
    """
    Fetch the children of the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch the children of.

    Returns
    -------
    list[Pooch]
        A list of Pooch ORM objects representing the pooch's children.
    """

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(PoochParentage, PoochParentage.child_id == Pooch.id)
            .where(or_(PoochParentage.father_id == pooch_id, PoochParentage.mother_id == pooch_id))
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        children = list((await session.execute(query)).scalars().all())

    return children


async def list_pooch_siblings(pooch_id: int) -> list[Pooch]:
    """
    Fetch the full siblings of the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch the full siblings of.

    Returns
    -------
    list[Pooch]
        A list of Pooch ORM objects representing the pooch's full siblings (sharing both a mother and father).
    """

    father, mother = await get_pooch_parents(pooch_id)

    if not father or not mother:
        return []

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(PoochParentage, PoochParentage.child_id == Pooch.id)
            .where(
                Pooch.id != pooch_id,
                PoochParentage.father_id == father.id,
                PoochParentage.mother_id == mother.id,
            )
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        siblings = list((await session.execute(query)).scalars().all())

    return siblings


async def list_pooch_pregnancies() -> list[PoochPregnancy]:
    """
    Fetch a list of every all pooch pregnancy instances.

    Returns
    -------
    list[PoochPregnancy]
        The list of PoochPregnancy ORM relationship objects across all servers.
    """

    async with session_scope() as session:
        response = await session.execute(select(PoochPregnancy))

    return list(response.scalars().all())


async def list_vendors(server_discord_id: int) -> list[Vendor]:
    """
    Fetch the list of vendors for a given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to fetch the vendors of.

    Returns
    -------
    list[Vendor]
        The list of Vendor ORM objects belonging to the given server.
    """

    async with session_scope() as session:
        response = await session.execute(select(Vendor).where(Vendor.server_discord_id == server_discord_id))

    return list(response.scalars().all())


async def list_vendor_pooch_stock(vendor_id: int) -> list[Pooch]:
    """
    Fetch a list of every pooch a given vendor has for sale.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to fetch the pooches from.

    Returns
    -------
    list[Pooch]
        The list of Pooch ORM objects representing the pooches the given vendor has for sale.
    """

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(VendorPoochForSale, VendorPoochForSale.pooch_id == Pooch.id)
            .where(VendorPoochForSale.vendor_id == vendor_id)
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_servers() -> list[Server]:
    """
    Fetch a list of all servers in the database.

    Returns
    -------
    list[Server]
        The list of all Server ORM objects in the database.
    """

    async with session_scope() as session:
        query = select(Server)
        response = await session.execute(query)

    return list(response.scalars().all())
