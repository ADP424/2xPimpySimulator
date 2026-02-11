from typing import Optional
from sqlalchemy import delete, select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)

from .get import get_vendor_by_id, get_pooch_by_id


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
        The Pooch ORM object removed from the kennel, or None if it wasn't found.
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

    fetus = await get_pooch_by_id(fetus_id)

    if fetus is None:
        return None

    async with session_scope() as session:
        await session.execute(
            delete(PoochPregnancy).where(
                PoochPregnancy.mother_id == mother_id,
                PoochPregnancy.fetus_id == fetus_id,
            )
        )

    return fetus
