from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .session import make_engine, make_sessionmaker
from .models import *  # loads all ORM models (via database/models/__init__.py)

_ENGINE: Optional[AsyncEngine] = None
_SESSIONMAKER: Optional[async_sessionmaker[AsyncSession]] = None


def _get_engine() -> AsyncEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = make_engine()
    return _ENGINE


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _SESSIONMAKER
    if _SESSIONMAKER is None:
        _SESSIONMAKER = make_sessionmaker(_get_engine())
    return _SESSIONMAKER


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Yield an engine session and commit on success, rollback on error.
    Designed to be used like `async with session_scope() as session`.

    Returns
    -------
    AsyncIterator[AsyncSession]
        The yielded session.
    """

    sessionmaker = _get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_owner_by_discord_id(server_id: int, owner_discord_id: int) -> Optional[Owner]:
    async with session_scope() as session:
        query = select(Owner).where(Owner.server_id == server_id, Owner.discord_id == owner_discord_id)
        response = await session.execute(query)
        return response.scalar_one_or_none()


async def create_owner(server_id: int, owner_discord_id: int) -> Owner:
    async with session_scope() as session:
        owner = Owner(server_id=server_id, discord_id=owner_discord_id)
        session.add(owner)
        await session.flush()
        return owner


async def list_kennels_for_owner(server_id: int, owner_discord_id: int) -> list[Kennel]:
    async with session_scope() as session:
        query = (
            select(Kennel)
            .where(Kennel.server_id == server_id, Kennel.owner_discord_id == owner_discord_id)
            .order_by(Kennel.created_at.asc(), Kennel.id.asc())
        )
        response = await session.execute(query)
        return list(response.scalars().all())


async def list_pooches_for_kennel(server_id: int, kennel_id: int) -> list[Pooch]:
    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(KennelPooch, (KennelPooch.server_id == Pooch.server_id) & (KennelPooch.pooch_id == Pooch.id))
            .where(KennelPooch.server_id == server_id, KennelPooch.kennel_id == kennel_id)
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        response = await session.execute(query)
        return list(response.scalars().all())


async def get_pooch_by_id(server_id: int, pooch_id: int) -> Optional[Pooch]:
    async with session_scope() as session:
        query = select(Pooch).where(Pooch.server_id == server_id, Pooch.id == pooch_id)
        response = await session.execute(query)
        return response.scalar_one_or_none()


async def get_pooch_family(server_id: int, pooch_id: int) -> dict[str, list[Pooch]]:
    async with session_scope() as session:
        parent_query = select(PoochParentage).where(
            PoochParentage.server_id == server_id,
            PoochParentage.pooch_id == pooch_id,
        )
        parent_response = await session.execute(parent_query)
        parentage = parent_response.scalar_one_or_none()

        parents: list[Pooch] = []
        father_id = getattr(parentage, "father_id", None)
        mother_id = getattr(parentage, "mother_id", None)

        if father_id is not None:
            father = await session.get(Pooch, {"server_id": server_id, "id": father_id})
            if father is not None:
                parents.append(father)

        if mother_id is not None:
            mother = await session.get(Pooch, {"server_id": server_id, "id": mother_id})
            if mother is not None:
                parents.append(mother)

        children_query = (
            select(Pooch)
            .join(PoochParentage, (PoochParentage.server_id == Pooch.server_id) & (PoochParentage.pooch_id == Pooch.id))
            .where(
                PoochParentage.server_id == server_id,
                or_(PoochParentage.father_id == pooch_id, PoochParentage.mother_id == pooch_id),
            )
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        children_response = await session.execute(children_query)
        children = list(children_response.scalars().all())

        siblings: list[Pooch] = []
        sib_conditions = []
        if father_id is not None:
            sib_conditions.append(PoochParentage.father_id == father_id)
        if mother_id is not None:
            sib_conditions.append(PoochParentage.mother_id == mother_id)

        if sib_conditions:
            sib_query = (
                select(Pooch)
                .join(
                    PoochParentage,
                    (PoochParentage.server_id == Pooch.server_id) & (PoochParentage.pooch_id == Pooch.id),
                )
                .where(
                    PoochParentage.server_id == server_id,
                    Pooch.id != pooch_id,
                    or_(*sib_conditions),
                )
                .order_by(Pooch.created_at.asc(), Pooch.id.asc())
            )
            sib_response = await session.execute(sib_query)
            siblings = list(sib_response.scalars().all())

        return {"parents": parents, "children": children, "siblings": siblings}
