from typing import Optional

from sqlalchemy import delete, func, select

from .models import KennelPooch, Pooch, PoochPregnancy, Vendor, VendorPoochForSale
from .session import session_scope


async def clear_vendor_pooch_stock(vendor_id: int, delete_pooches: bool = False) -> Optional[Vendor]:
    """
    Clear the pooch stock of the vendor with the given ID.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to clear the stock of.

    delete_pooches: bool, default : False
        Whether to delete the Pooch ORM objects as well as removing them from the vendor.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object whose stock was just cleared, or None if the vendor wasn't found.
    """

    async with session_scope() as session:
        response = await session.execute(select(Vendor).where(Vendor.id == vendor_id))
        vendor = response.scalar_one_or_none()
        if vendor is None:
            return None

        if delete_pooches:
            await session.execute(
                delete(Pooch)
                .where(VendorPoochForSale.pooch_id == Pooch.id)
                .where(VendorPoochForSale.vendor_id == vendor_id)
            )
        else:
            await session.execute(delete(VendorPoochForSale).where(VendorPoochForSale.vendor_id == vendor_id))

    return vendor


async def delete_pooch(pooch_id: int) -> Optional[Pooch]:
    """
    Delete a pooch ORM object completely from the database.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch object to delete.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object that was just permanently deleted, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        response = await session.execute(select(Pooch).where(Pooch.id == pooch_id))
        pooch = response.scalar_one_or_none()
        if pooch is None:
            return None

        await session.execute(delete(Pooch).where(Pooch.id == pooch_id))

    return pooch


async def delete_pregnancy(mother_id: int, fetus_id: int) -> Optional[Pooch]:
    """
    Delete a pooch pregnancy instance.

    Parameters
    ----------
    mother_id: int
        The ID of the mother pooch.

    fetus_id: int
        The ID of the fetal pooch.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object representing the fetus from the pregnancy that just ended.
    """

    async with session_scope() as session:
        response = await session.execute(select(Pooch).where(Pooch.id == fetus_id))
        fetus = response.scalar_one_or_none()
        if fetus is None:
            return None

        await session.execute(
            delete(PoochPregnancy).where(
                PoochPregnancy.mother_id == mother_id,
                PoochPregnancy.fetus_id == fetus_id,
            )
        )

    return fetus


async def delete_random_vendor(server_discord_id: int) -> Optional[Vendor]:
    """
    Delete a random vendor from the server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The ID of the server to randomly remove a vendor from.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object removed, or None if the server has no vendors.
    """

    async with session_scope() as session:
        vendor = await session.scalar(
            select(Vendor).where(Vendor.server_discord_id == server_discord_id).order_by(func.random()).limit(1)
        )

        if vendor is None:
            return None

        await session.delete(vendor)
        await session.flush()

        return vendor


async def remove_pooch_from_kennel(pooch_id: int) -> Pooch:
    """
    Remove the pooch with the given ID from the kennel it's in, if any.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to remove from its kennel.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object removed from the kennel, or None if the pooch wasn't found in a kennel.
    """

    async with session_scope() as session:
        response = await session.execute(
            select(Pooch)
            .join(KennelPooch, KennelPooch.pooch_id == Pooch.id)
            .where(
                KennelPooch.pooch_id == pooch_id,
            )
        )
        pooch = response.scalar_one_or_none()

        if not pooch:
            return None

        response = await session.execute(
            delete(KennelPooch).where(
                KennelPooch.pooch_id == pooch_id,
            )
        )

    return pooch


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
        The Pooch that was removed from the vendor's inventory, or None if no pooch with the given ID
        was found in the given vendor's inventory.
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
