from typing import Optional

from sqlalchemy import delete, select, or_

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)


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
            PoochParentage.child_id == pooch_id,
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
            .join(PoochParentage, (PoochParentage.server_id == Pooch.server_id) & (PoochParentage.child_id == Pooch.id))
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
                    (PoochParentage.server_id == Pooch.server_id) & (PoochParentage.child_id == Pooch.id),
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


async def set_event_channel_id(server_id: int, channel_id: int):
    async with session_scope() as session:
        server = await session.get(Server, {"server_id": server_id})
        if server is not None:
            server.event_channel_id = channel_id
            session.add(server)


async def get_event_channel_id(server_id: int) -> Optional[int]:
    async with session_scope() as session:
        server = await session.get(Server, {"server_id": server_id})
        return None if server is None else int(server.event_channel_id)


async def list_alive_player_pooches_all_servers() -> list[Pooch]:
    async with session_scope() as session:
        statement = select(Pooch).where(Pooch.alive == True, Pooch.vendor_id.is_(None))
        response = await session.execute(statement)
        return list(response.scalars().all())


async def get_pooch_kennel(server_id: int, pooch_id: int) -> Optional[int]:
    async with session_scope() as session:
        statement = (
            select(KennelPooch.kennel_id)
            .where(KennelPooch.server_id == server_id, KennelPooch.pooch_id == pooch_id)
            .limit(1)
        )
        response = await session.execute(statement)
        kennel_id = response.scalar_one_or_none()
        return None if kennel_id is None else int(kennel_id)


async def add_pooch_to_kennel(server_id: int, kennel_id: int, pooch_id: int):
    async with session_scope() as session:
        session.add(KennelPooch(server_id=server_id, kennel_id=kennel_id, pooch_id=pooch_id))


async def remove_pooch_from_kennels(server_id: int, pooch_id: int):
    async with session_scope() as session:
        await session.execute(
            delete(KennelPooch).where(KennelPooch.server_id == server_id, KennelPooch.pooch_id == pooch_id)
        )


async def create_newborn_pooch(
    *, server_id: int, owner_discord_id: int | None, name: str, sex: str, base_health: int
) -> Pooch:
    async with session_scope() as session:
        pooch = Pooch(
            server_id=server_id,
            owner_discord_id=owner_discord_id,
            name=name,
            sex=sex,
            age=0,
            base_health=base_health,
            health_loss_age=0,
            alive=True,
        )
        session.add(pooch)
        await session.flush()
        return pooch


async def list_pregnancies() -> list[PoochPregnancy]:
    async with session_scope() as session:
        res = await session.execute(select(PoochPregnancy))
        return list(res.scalars().all())


async def delete_pregnancy(server_id: int, mother_id: int, fetus_id: int):
    async with session_scope() as session:
        await session.execute(
            delete(PoochPregnancy).where(
                PoochPregnancy.server_id == server_id,
                PoochPregnancy.mother_id == mother_id,
                PoochPregnancy.fetus_id == fetus_id,
            )
        )


async def decrement_breeding_cooldown(server_id: int, pooch_id: int):
    async with session_scope() as session:
        pooch = await session.get(Pooch, {"server_id": server_id, "id": pooch_id})
        if pooch is None:
            return
        pooch.breeding_cooldown = max(int(getattr(pooch, "breeding_cooldown", 0)) - 1, 0)
        session.add(pooch)


async def age_pooch(server_id: int, pooch_id: int) -> Optional[Pooch]:
    async with session_scope() as session:
        pooch = await session.get(Pooch, {"server_id": server_id, "id": pooch_id})
        if pooch is None:
            return None
        pooch.age = int(getattr(pooch, "age", 0)) + 1
        if int(pooch.age) > 5:
            pooch.health_loss_age = int(getattr(pooch, "health_loss_age", 0)) + 1
        session.add(pooch)
        return pooch


async def set_pooch_dead(server_id: int, pooch_id: int):
    async with session_scope() as session:
        pooch = await session.get(Pooch, {"server_id": server_id, "id": pooch_id})
        if pooch is None:
            return
        pooch.alive = False
        session.add(pooch)


async def bury_pooch(server_id: int, owner_discord_id: int, pooch_id: int):
    async with session_scope() as session:
        session.add(GraveyardPooch(server_id=server_id, owner_discord_id=owner_discord_id, pooch_id=pooch_id))


async def list_vendors(server_id: int) -> list[Vendor]:
    async with session_scope() as session:
        res = await session.execute(select(Vendor).where(Vendor.server_id == server_id))
        return list(res.scalars().all())


async def clear_vendor_stock(server_id: int, vendor_id: int):
    async with session_scope() as session:
        await session.execute(
            delete(VendorPoochForSale).where(
                VendorPoochForSale.server_id == server_id,
                VendorPoochForSale.vendor_id == vendor_id,
            )
        )


async def add_vendor_stock(server_id: int, vendor_id: int, pooch_id: int, price: int):
    async with session_scope() as session:
        session.add(VendorPoochForSale(server_id=server_id, vendor_id=vendor_id, pooch_id=pooch_id, price=price))
