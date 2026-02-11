from typing import Optional
from sqlalchemy import delete, func, select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)

from .pooch_manager import get_pooch_by_id


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


async def create_vendor(server_discord_id: int, name: Optional[str] = None) -> Optional[Vendor]:
    """
    Fetch the list of vendors for a given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to create the vendor in.

    name: str, optional
        The name to give the new vendor. Chooses a random one if not given.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object that was just created, or None if the server with the given ID wasn't found.
    """

    async def _get_random_vendor_name():
        statement = select(VendorFirstName).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        first_name = response.scalar_one_or_none()

        statement = select(VendorLastName).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        last_name = response.scalar_one_or_none()

        return f"{(first_name.name + ' ') if first_name is not None else ''}{last_name.name if last_name is not None else ''}"

    # TODO: Add random desired mutations

    async with session_scope() as session:
        vendor = Vendor(server_discord_id=server_discord_id, name=name or await _get_random_vendor_name())
        session.add(vendor)
        await session.flush()

    return vendor


async def add_pooch_to_vendor_stock(vendor_id: int, pooch_id: int) -> Optional[VendorPoochForSale]:
    """
    Add the pooch with the given ID to the given vendor's stock.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor whose stock the pooch will be added to.

    pooch_id: int
        The ID of the pooch to add to the given vendor's stock.

    Returns
    -------
    VendorPoochForSale, optional
        The VendorPoochForSale ORM object that was just created, or None if the vendor or pooch wasn't found.
    """

    vendor = await get_vendor_by_id(vendor_id)
    pooch = await get_pooch_by_id(pooch_id)

    if vendor is None or pooch is None:
        return None

    async with session_scope() as session:
        vendor_pooch_for_sale = VendorPoochForSale(vendor_id=vendor.id, pooch_id=pooch.id)
        session.add(vendor_pooch_for_sale)

    return vendor_pooch_for_sale


async def clear_vendor_pooch_stock(vendor_id: int) -> Optional[Vendor]:
    """
    Clear the pooch stock of the vendor with the given ID.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to clear the stock of.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object whose stock was just cleared, or None if the vendor wasn't found.
    """

    vendor = await get_vendor_by_id(vendor_id)

    if vendor is None:
        return None

    async with session_scope() as session:
        await session.execute(delete(VendorPoochForSale).where(VendorPoochForSale.vendor_id == vendor_id))

    return vendor


async def remove_pooch_from_vendor_stock(vendor_id: int, pooch_id: int) -> Optional[Pooch]:
    """
    Remove the pooch with the given ID from the given vendor's inventory.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor that owns the pooch to be removed.

    pooch_id: int
        The ID of the pooch to remove from the vendor's inventory.

    Returns
    -------
    Pooch, optional
        The Pooch that was removed from the vendor's inventory, or None if no pooch with the given ID was found in the given vendor's inventory.
    """

    async with session_scope() as session:
        response = await session.execute(
            select(Pooch)
            .join(VendorPoochForSale, VendorPoochForSale.pooch_id == Pooch.id)
            .where(
                VendorPoochForSale.vendor_id == vendor_id,
                VendorPoochForSale.pooch_id == pooch_id,
            )
        )
        pooch = response.scalar_one_or_none()

        if not pooch:
            return None

        response = await session.execute(
            delete(VendorPoochForSale).where(
                VendorPoochForSale.vendor_id == vendor_id,
                VendorPoochForSale.pooch_id == pooch_id,
            )
        )

    return pooch
