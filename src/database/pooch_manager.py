import random
from typing import Optional
from sqlalchemy import cast, delete, func, or_, select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)
from .models.enums.sex import SEX

from .owner_manager import get_owner_by_discord_id
from .vendor_manager import get_vendor_by_id


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


async def create_pooch(
    owner_discord_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    name: Optional[str] = None,
    sex: Optional[str] = None,
    age: int = -1,
    base_health: Optional[int] = None,
) -> Pooch:
    """
    Create a pooch.

    Parameters
    ----------
    owner_discord_id: int, optional
        The Discord ID of the owner to own the new pooch, if any.

    vendor_id: int, optional
        The ID of the vendor to own the new pooch, if any.

    name: str, optional
        The name to give the pooch. Chooses a random one if not given.

    sex: str, optional
        The sex to give the pooch. Chooses a random one if not given.

    age: int, default = -1
        The age to make the pooch. Defaults to -1 (fetal age).

    base_health: int, optional
        The base health to give the pooch. Chooses randomly within a range if not given.

    Returns
    -------
    Pooch
        The Pooch ORM object that was just created.
    """

    async def _get_random_pooch_name():
        statement = select(DogName).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        dog_name = response.scalar_one_or_none()
        return dog_name.name if dog_name is not None else "Dog"

    async def _get_random_sex():
        statement = select(func.unnest(func.enum_range(cast(None, SEX)))).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        s = response.scalar_one_or_none()
        return s if s is not None else "female"

    if owner_discord_id is not None:
        owner = await get_owner_by_discord_id(owner_discord_id)
        if owner is None:
            owner_discord_id = None

    if vendor_id is not None:
        vendor = await get_vendor_by_id(vendor_id)
        if vendor is None:
            vendor_id = None

    # if both owner and vendor are provided, prioritize owner
    if owner_discord_id is not None and vendor_id is not None:
        vendor_id = None

    async with session_scope() as session:
        pooch = Pooch(
            owner_discord_id=owner_discord_id,
            vendor_id=vendor_id,
            name=name or await _get_random_pooch_name(),
            sex=sex or await _get_random_sex(),
            age=age,
            base_health=base_health or random.randint(8, 12),  # TODO
            health_loss_age=0,  # TODO
            breeding_cooldown=2,  # TODO
            alive=True,
            virgin=True,
        )
        session.add(pooch)
        await session.flush()

    return pooch


async def age_pooch(pooch_id: int) -> Optional[Pooch]:
    """
    Age the pooch with the given ID by 1, and increase its age health loss if it's old enough.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to age.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object that just aged, or None if the pooch wasn't found.
    """

    pooch = await get_pooch_by_id(pooch_id)

    if pooch is None:
        return None

    pooch.age += 1
    if pooch.age > 5:  # TODO
        pooch.health_loss_age += 1

    return pooch


async def decrement_pooch_breeding_cooldown(pooch_id: int) -> Optional[Pooch]:
    """
    Decrease the breeding cooldown of the pooch with the given ID by 1, to a minimum of 0.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to decrease the breeding cooldown of.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object whose breeding cooldown just decreased.
    """

    pooch = await get_pooch_by_id(pooch_id)

    if pooch is None:
        return None

    pooch.breeding_cooldown = max(pooch.breeding_cooldown - 1, 0)
    return pooch


async def set_pooch_dead(pooch_id: int) -> Optional[Pooch]:
    """
    Set the pooch with the given ID to dead.
    Doesn't move the pooch to a graveyard. Call `bury_pooch` to do that.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to kill.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object that was just killed.
    """

    pooch = await get_pooch_by_id(pooch_id)

    if pooch is None:
        return None

    pooch.alive = False
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
