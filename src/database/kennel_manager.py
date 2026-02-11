from typing import Optional
from sqlalchemy import delete, select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)

from .owner_manager import get_owner_by_discord_id


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


async def create_kennel(owner_discord_id: int, name: str = "Kennel", pooch_limit: int = 10) -> Optional[Kennel]:  # TODO
    """
    Create a kennel for the given owner.

    Parameters
    ----------
    owner_discord_id: int
        The discord ID of the owner to create the kennel for.

    name: str, default: "Kennel"
        The name to give the new kennel.

    pooch_limit: int, default: 10
        The size limit to give the new kennel.

    Returns
    -------
    Kennel, optional
        The newly created Kennel, or None if the owner with the given Discord ID couldn't be found.
    """

    owner = get_owner_by_discord_id(owner_discord_id)

    if owner is None:
        return None

    async with session_scope() as session:
        kennel = Kennel(
            owner_discord_id=owner.discord_id,
            name=name,
            pooch_limit=pooch_limit,
        )
        session.add(kennel)
        await session.flush()

    return kennel


async def add_pooch_to_kennel(kennel_id: int, pooch_id: int) -> KennelPooch:
    """
    Add the pooch with the given ID to the kennel with the given ID.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to add the pooch to.

    pooch_id: int
        The ID of the pooch to add to the kennel.

    Returns
    -------
    KennelPooch
        The KennelPooch relationship ORM object just created.
    """

    async with session_scope() as session:
        kennel_pooch = KennelPooch(kennel_id=kennel_id, pooch_id=pooch_id)
        session.add(kennel_pooch)
        await session.flush()

    return kennel_pooch


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
