from sqlalchemy import or_, select

from .session import session_scope
from .get import get_pooch_parents

from .models import *  # loads all ORM models (via database/models/__init__.py)


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
        query = select(Pooch).where(Pooch.alive == True).order_by(Pooch.created_at.asc(), Pooch.id.asc())
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
        response = await session.execute(select(PoochPregnancy).order_by(PoochPregnancy.fetus_id.asc()))

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
        response = await session.execute(
            select(Vendor)
            .where(Vendor.server_discord_id == server_discord_id)
            .order_by(Vendor.name.asc(), Vendor.id.asc())
        )

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


async def list_servers_for_pooch(pooch_id: int) -> list[Server]:
    """
    Fetch a list of all the servers in which a pooch is relevant.
    A pooch is relevant in a server if their owner is in the server (player or vendor).

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the servers for.

    Returns
    -------
    list[Server]
        The list of Server ORM objects the given pooch vicariously belongs to.
    """

    async with session_scope() as session:
        query = (
            select(Server)
            .join(Vendor, Vendor.server_discord_id == Server.discord_id)
            .join(OwnerServer, OwnerServer.server_discord_id == Server.discord_id)
            .join(Pooch, or_(Pooch.vendor_id == Vendor.id, Pooch.owner_discord_id == OwnerServer.owner_discord_id))
            .where(Pooch.id == pooch_id)
            .order_by(Server.joined_at.asc(), Server.discord_id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_owner_servers(owner_discord_id: int) -> list[Server]:
    """
    Fetch a list of all the servers the owner with the given Discord ID is in.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to get the servers for.

    Returns
    -------
    list[Server]
        The list of Server ORM objects the given owner belongs to.
    """

    async with session_scope() as session:
        query = (
            select(Server)
            .join(OwnerServer, OwnerServer.server_discord_id == Server.discord_id)
            .where(OwnerServer.owner_discord_id == owner_discord_id)
            .order_by(Server.joined_at.asc(), Server.discord_id.asc())
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
        query = select(Server).order_by(Server.joined_at.asc(), Server.discord_id.asc())
        response = await session.execute(query)

    return list(response.scalars().all())
