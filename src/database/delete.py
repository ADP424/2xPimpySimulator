import random
from typing import Optional

from sqlalchemy import and_, delete, func, or_, select

from src.database.models.enums.health_impact_weight import HealthImpactWeight

from .models import (
    KennelPooch,
    Mutation,
    Pooch,
    PoochMutation,
    PoochPregnancy,
    StrayPooch,
    Vendor,
    VendorPoochForSale,
)
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


async def remove_mutation_from_pooch(pooch_id: int, mutation_id: int) -> Optional[PoochMutation]:
    """
    Remove a mutation from a pooch.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to remove the mutation from.

    mutation_id: int
        The ID of the mutation to remove.

    Returns
    -------
    PoochMutation, optional
        The removed PoochMutation relationship, or None if it didn't exist.
    """

    async with session_scope() as session:
        query = select(PoochMutation).where(
            and_(
                PoochMutation.pooch_id == pooch_id,
                PoochMutation.mutation_id == mutation_id,
            )
        )
        result = await session.execute(query)
        pooch_mutation = result.scalar_one_or_none()

        if pooch_mutation is not None:
            await session.delete(pooch_mutation)

        return pooch_mutation


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


async def remove_pooch_from_strays(pooch_id: int) -> Optional[StrayPooch]:
    """
    Remove the given pooch from the stray pool.

    Parameters
    ----------
    pooch_id: int
        The ID of the stray pooch to remove.

    Returns
    -------
    StrayPooch, optional
        The removed StrayPooch ORM object, or None if it wasn't in the stray pool.
    """

    async with session_scope() as session:
        stray = await session.get(StrayPooch, pooch_id)
        if stray is None:
            return None
        await session.delete(stray)
        return stray


async def remove_random_mutation_from_pooch(
    pooch_id: int,
    rng: Optional[random.Random] = None,
    positive: bool = True,
    negative: bool = True,
    neutral: bool = True,
) -> Optional[PoochMutation]:
    """
    Remove a random mutation from a pooch.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to remove a mutation from.

    rng: Random, optional
        The random generator to use for selection.

    positive: bool
        Whether to include positive health impact mutations.

    negative: bool
        Whether to include negative health impact mutations.

    neutral: bool
        Whether to include neutral health impact mutations.

    Returns
    -------
    PoochMutation, optional
        The removed PoochMutation relationship, or None if the pooch had no mutations.
    """

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:
        weight_conditions = []
        if positive:
            weight_conditions.append(HealthImpactWeight.weight > 0)
        if negative:
            weight_conditions.append(HealthImpactWeight.weight < 0)
        if neutral:
            weight_conditions.append(HealthImpactWeight.weight == 0)

        if not weight_conditions:
            return None

        query = (
            select(PoochMutation)
            .join(Mutation, Mutation.id == PoochMutation.mutation_id)
            .join(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(
                and_(
                    PoochMutation.pooch_id == pooch_id,
                    or_(*weight_conditions),
                )
            )
        )
        result = await session.execute(query)
        mutations = list(result.scalars().all())

        if not mutations:
            return None

        selected = rng.choice(mutations)
        await session.delete(selected)

        return selected
