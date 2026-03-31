from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Select, and_, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Breed,
    GraveyardPooch,
    HealthImpactWeight,
    HellPooch,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    Pooch,
    PoochBreed,
    PoochMutation,
    StrayPooch,
)

if TYPE_CHECKING:
    from ..models.event_types import (
        KennelFilterSpec,
        OwnerEventFilterSpec,
        PoochFilterSpec,
        ServerEventFilterSpec,
        StrayEventFilterSpec,
    )

_FILTER_META_KEYS = {"min_count", "max_count", "description"}


def _is_excluded(value: int | float, exclude_list: list | None) -> bool:
    if not exclude_list:
        return False
    return int(value) in exclude_list


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _strip_requirement_metadata(
    filter_spec: OwnerEventFilterSpec | PoochFilterSpec | KennelFilterSpec,
) -> OwnerEventFilterSpec | PoochFilterSpec | KennelFilterSpec:
    return {key: value for key, value in filter_spec.items() if key not in _FILTER_META_KEYS}


async def _get_breed_ids_by_names(session: AsyncSession, names: list[str]) -> list[int]:
    normalized = [_normalize_name(name) for name in names if isinstance(name, str) and name.strip()]
    if not normalized:
        return []

    result = await session.execute(select(Breed.id).where(func.lower(Breed.name).in_(normalized)))
    return list(result.scalars().all())


async def _get_mutation_ids_by_names(session: AsyncSession, names: list[str]) -> list[int]:
    normalized = [_normalize_name(name) for name in names if isinstance(name, str) and name.strip()]
    if not normalized:
        return []

    result = await session.execute(select(Mutation.id).where(func.lower(Mutation.name).in_(normalized)))
    return list(result.scalars().all())


async def _build_pooch_query(
    session: AsyncSession,
    filter_spec: PoochFilterSpec | None,
    owner_discord_id: Optional[int] = None,
    kennel_id: Optional[int] = None,
) -> Select[tuple[Pooch]]:
    filter_spec = {} if filter_spec is None else filter_spec
    filter_spec.pop("min_count", None)
    filter_spec.pop("max_count", None)
    filter_spec.pop("description", None)

    query: Select[tuple[Pooch]] = select(Pooch)
    conditions = []

    if owner_discord_id is not None:
        conditions.append(Pooch.owner_discord_id == owner_discord_id)

    if kennel_id is not None:
        kennel_members_subquery = select(KennelPooch.pooch_id).where(KennelPooch.kennel_id == kennel_id)
        conditions.append(Pooch.id.in_(kennel_members_subquery))

    if filter_spec.get("min_age") is not None:
        conditions.append(Pooch.age >= filter_spec["min_age"])
    if filter_spec.get("max_age") is not None:
        conditions.append(Pooch.age <= filter_spec["max_age"])
    if filter_spec.get("exclude_age"):
        conditions.append(Pooch.age.not_in(filter_spec["exclude_age"]))

    if filter_spec.get("sex") is not None:
        conditions.append(Pooch.sex == str(filter_spec["sex"]).strip().lower())

    if (
        filter_spec.get("min_health") is not None
        or filter_spec.get("max_health") is not None
        or filter_spec.get("exclude_health")
    ):
        mutation_health_subquery = (
            select(func.coalesce(func.sum(HealthImpactWeight.weight), 0))
            .join(Mutation, Mutation.health_impact == HealthImpactWeight.health_impact)
            .join(PoochMutation, PoochMutation.mutation_id == Mutation.id)
            .where(PoochMutation.pooch_id == Pooch.id)
            .correlate(Pooch)
            .scalar_subquery()
        )
        effective_health = Pooch.base_health - Pooch.health_loss_age + mutation_health_subquery
        if filter_spec.get("min_health") is not None:
            conditions.append(effective_health >= filter_spec["min_health"])
        if filter_spec.get("max_health") is not None:
            conditions.append(effective_health <= filter_spec["max_health"])
        if filter_spec.get("exclude_health"):
            conditions.append(effective_health.not_in(filter_spec["exclude_health"]))

    if filter_spec.get("is_virgin") is not None:
        conditions.append(Pooch.virgin.is_(bool(filter_spec["is_virgin"])))
    if filter_spec.get("is_alive") is not None:
        conditions.append(Pooch.alive.is_(bool(filter_spec["is_alive"])))

    if filter_spec.get("min_breeding_cooldown") is not None:
        conditions.append(Pooch.breeding_cooldown >= filter_spec["min_breeding_cooldown"])
    if filter_spec.get("max_breeding_cooldown") is not None:
        conditions.append(Pooch.breeding_cooldown <= filter_spec["max_breeding_cooldown"])
    if filter_spec.get("exclude_breeding_cooldown"):
        conditions.append(Pooch.breeding_cooldown.not_in(filter_spec["exclude_breeding_cooldown"]))

    location = filter_spec.get("location")
    if isinstance(location, str):
        normalized_location = location.strip().lower()
        kennel_members_subquery = select(KennelPooch.pooch_id).distinct()
        if normalized_location == "kennel":
            conditions.append(Pooch.id.in_(kennel_members_subquery))
        elif normalized_location == "graveyard":
            graveyard_subquery = select(GraveyardPooch.pooch_id).distinct()
            conditions.append(Pooch.id.in_(graveyard_subquery))
        elif normalized_location == "hell":
            hell_subquery = select(HellPooch.pooch_id).distinct()
            conditions.append(Pooch.id.in_(hell_subquery))
        elif normalized_location == "town":
            stray_subquery = select(StrayPooch.pooch_id).distinct()
            conditions.append(Pooch.id.in_(stray_subquery))
        # "all", "any" — no location restriction

    if conditions:
        query = query.where(and_(*conditions))

    if filter_spec.get("has_any_breed"):
        breed_ids = await _get_breed_ids_by_names(session, list(filter_spec["has_any_breed"]))
        if not breed_ids:
            return query.where(false())
        breed_subquery = select(PoochBreed.pooch_id).where(PoochBreed.breed_id.in_(breed_ids)).distinct()
        query = query.where(Pooch.id.in_(breed_subquery))

    if filter_spec.get("has_all_breeds"):
        breed_ids = await _get_breed_ids_by_names(session, list(filter_spec["has_all_breeds"]))
        if not breed_ids:
            return query.where(false())
        for breed_id in breed_ids:
            breed_subquery = select(PoochBreed.pooch_id).where(PoochBreed.breed_id == breed_id)
            query = query.where(Pooch.id.in_(breed_subquery))

    if filter_spec.get("exclude_breeds"):
        breed_ids = await _get_breed_ids_by_names(session, list(filter_spec["exclude_breeds"]))
        if breed_ids:
            breed_subquery = select(PoochBreed.pooch_id).where(PoochBreed.breed_id.in_(breed_ids)).distinct()
            query = query.where(Pooch.id.not_in(breed_subquery))

    if filter_spec.get("has_any_mutation"):
        mutation_ids = await _get_mutation_ids_by_names(session, list(filter_spec["has_any_mutation"]))
        if not mutation_ids:
            return query.where(false())
        mutation_subquery = select(PoochMutation.pooch_id).where(PoochMutation.mutation_id.in_(mutation_ids)).distinct()
        query = query.where(Pooch.id.in_(mutation_subquery))

    if filter_spec.get("has_all_mutations"):
        mutation_ids = await _get_mutation_ids_by_names(session, list(filter_spec["has_all_mutations"]))
        if not mutation_ids:
            return query.where(false())
        for mutation_id in mutation_ids:
            mutation_subquery = select(PoochMutation.pooch_id).where(PoochMutation.mutation_id == mutation_id)
            query = query.where(Pooch.id.in_(mutation_subquery))

    if filter_spec.get("exclude_mutations"):
        mutation_ids = await _get_mutation_ids_by_names(session, list(filter_spec["exclude_mutations"]))
        if mutation_ids:
            mutation_subquery = (
                select(PoochMutation.pooch_id).where(PoochMutation.mutation_id.in_(mutation_ids)).distinct()
            )
            query = query.where(Pooch.id.not_in(mutation_subquery))

    return query


async def count_matching_pooches_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: PoochFilterSpec | None,
    kennel_id: Optional[int] = None,
) -> int:
    query = await _build_pooch_query(session, filter_spec, owner_discord_id=owner_discord_id, kennel_id=kennel_id)
    count_query = select(func.count()).select_from(query.subquery())
    result = await session.scalar(count_query)
    return result or 0


async def get_matching_pooch_ids_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: PoochFilterSpec | None,
    kennel_id: Optional[int] = None,
) -> list[int]:
    query = await _build_pooch_query(session, filter_spec, owner_discord_id=owner_discord_id, kennel_id=kennel_id)
    result = await session.execute(query.with_only_columns(Pooch.id))
    return [pooch_id for pooch_id in result.scalars().all()]


async def get_random_matching_pooch_id_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: PoochFilterSpec | None,
    rng: random.Random,
    kennel_id: Optional[int] = None,
) -> Optional[int]:
    pooch_ids = await get_matching_pooch_ids_for_owner(
        session,
        owner_discord_id,
        filter_spec,
        kennel_id=kennel_id,
    )
    if not pooch_ids:
        return None
    return rng.choice(pooch_ids)


async def _get_candidate_kennel_ids_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: KennelFilterSpec | None,
) -> list[int]:
    filter_spec = dict(filter_spec or {})
    filter_spec.pop("min_count", None)
    filter_spec.pop("max_count", None)
    filter_spec.pop("description", None)

    conditions = [Kennel.owner_discord_id == owner_discord_id]
    if filter_spec.get("min_capacity") is not None:
        conditions.append(Kennel.pooch_limit >= filter_spec["min_capacity"])
    if filter_spec.get("max_capacity") is not None:
        conditions.append(Kennel.pooch_limit <= filter_spec["max_capacity"])
    if filter_spec.get("exclude_capacity"):
        conditions.append(Kennel.pooch_limit.not_in(filter_spec["exclude_capacity"]))
    if filter_spec.get("min_upgrade_tier") is not None:
        conditions.append(Kennel.upgrade_tier >= filter_spec["min_upgrade_tier"])
    if filter_spec.get("max_upgrade_tier") is not None:
        conditions.append(Kennel.upgrade_tier <= filter_spec["max_upgrade_tier"])
    if filter_spec.get("exclude_upgrade_tier"):
        conditions.append(Kennel.upgrade_tier.not_in(filter_spec["exclude_upgrade_tier"]))

    query = select(Kennel.id).where(and_(*conditions))

    pooch_count_subquery = (
        select(KennelPooch.kennel_id, func.count(KennelPooch.pooch_id).label("pooch_count"))
        .group_by(KennelPooch.kennel_id)
        .subquery()
    )
    min_pooches = filter_spec.get("min_pooches")
    max_pooches = filter_spec.get("max_pooches")
    exclude_pooches = filter_spec.get("exclude_pooches")
    if min_pooches is not None:
        query = query.where(
            Kennel.id.in_(
                select(pooch_count_subquery.c.kennel_id).where(pooch_count_subquery.c.pooch_count >= min_pooches)
            )
        )
    if max_pooches is not None:
        if max_pooches < 0:
            # Negative value means relative to capacity: -1 = capacity - 1, etc.
            query = query.where(
                Kennel.id.not_in(
                    select(pooch_count_subquery.c.kennel_id)
                    .join(Kennel, Kennel.id == pooch_count_subquery.c.kennel_id)
                    .where(pooch_count_subquery.c.pooch_count > (Kennel.pooch_limit + max_pooches))
                )
            )
        else:
            query = query.where(
                Kennel.id.not_in(
                    select(pooch_count_subquery.c.kennel_id).where(pooch_count_subquery.c.pooch_count > max_pooches)
                )
            )
    if exclude_pooches:
        query = query.where(
            Kennel.id.not_in(
                select(pooch_count_subquery.c.kennel_id).where(pooch_count_subquery.c.pooch_count.in_(exclude_pooches))
            )
        )
    at_capacity = filter_spec.get("at_capacity")
    if at_capacity is True:
        query = query.where(
            Kennel.id.in_(
                select(pooch_count_subquery.c.kennel_id)
                .join(Kennel, Kennel.id == pooch_count_subquery.c.kennel_id)
                .where(pooch_count_subquery.c.pooch_count >= Kennel.pooch_limit)
            )
        )
    elif at_capacity is False:
        query = query.where(
            Kennel.id.not_in(
                select(pooch_count_subquery.c.kennel_id)
                .join(Kennel, Kennel.id == pooch_count_subquery.c.kennel_id)
                .where(pooch_count_subquery.c.pooch_count >= Kennel.pooch_limit)
            )
        )

    result = await session.execute(query)
    return [kennel_id for kennel_id in result.scalars().all()]


async def get_matching_kennel_ids_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: KennelFilterSpec | None,
) -> list[int]:
    filter_spec = dict(filter_spec or {})
    nested_pooch_filters = list(filter_spec.get("pooches", []))
    kennel_ids = await _get_candidate_kennel_ids_for_owner(session, owner_discord_id, filter_spec)
    if not nested_pooch_filters:
        return kennel_ids

    matching_kennel_ids: list[int] = []
    for kennel_id in kennel_ids:
        passes_all = True
        for pooch_filter in nested_pooch_filters:
            min_count = pooch_filter.get("min_count", 1)
            max_count = pooch_filter.get("max_count")
            count = await count_matching_pooches_for_owner(
                session,
                owner_discord_id,
                _strip_requirement_metadata(pooch_filter),
                kennel_id=kennel_id,
            )
            if count < min_count:
                passes_all = False
                break
            if max_count is not None and count > max_count:
                passes_all = False
                break
        if passes_all:
            matching_kennel_ids.append(kennel_id)

    return matching_kennel_ids


async def count_matching_kennels_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: KennelFilterSpec | None,
) -> int:
    return len(await get_matching_kennel_ids_for_owner(session, owner_discord_id, filter_spec))


async def get_random_matching_kennel_id_for_owner(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: KennelFilterSpec | None,
    rng: random.Random,
) -> Optional[int]:
    kennel_ids = await get_matching_kennel_ids_for_owner(session, owner_discord_id, filter_spec)
    if not kennel_ids:
        return None
    return rng.choice(kennel_ids)


async def _count_graveyard_pooches_for_owner(
    session: AsyncSession, owner_discord_id: int, filter_spec: "PoochFilterSpec | None"
) -> int:
    """Count dead pooches in this owner's graveyard that match the filter."""
    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)
    query = await _build_pooch_query(session, base_filter, owner_discord_id=owner_discord_id)
    graveyard_subquery = select(GraveyardPooch.pooch_id).distinct()
    query = query.where(Pooch.id.in_(graveyard_subquery))
    count_query = select(func.count()).select_from(query.subquery())
    return (await session.scalar(count_query)) or 0


async def _count_hell_pooches_for_owner(
    session: AsyncSession, owner_discord_id: int, filter_spec: "PoochFilterSpec | None"
) -> int:
    """Count pooches in hell owned by this owner that match the filter."""
    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)
    query = await _build_pooch_query(session, base_filter, owner_discord_id=owner_discord_id)
    hell_subquery = select(HellPooch.pooch_id).distinct()
    query = query.where(Pooch.id.in_(hell_subquery))
    count_query = select(func.count()).select_from(query.subquery())
    return (await session.scalar(count_query)) or 0


async def _get_owner_counts(session: AsyncSession, owner_discord_id: int) -> tuple[Owner | None, int, int]:
    owner = await session.scalar(select(Owner).where(Owner.discord_id == owner_discord_id))
    if owner is None:
        return None, 0, 0

    pooch_count = await session.scalar(select(func.count(Pooch.id)).where(Pooch.owner_discord_id == owner_discord_id))
    kennel_count = await session.scalar(
        select(func.count(Kennel.id)).where(Kennel.owner_discord_id == owner_discord_id)
    )
    return owner, pooch_count or 0, kennel_count or 0


async def check_owner_event_filter(
    session: AsyncSession,
    owner_discord_id: int,
    filter_spec: OwnerEventFilterSpec | None,
    season: Optional[str] = None,
) -> bool:
    if not filter_spec:
        owner_exists = await session.scalar(select(Owner.discord_id).where(Owner.discord_id == owner_discord_id))
        return owner_exists is not None

    seasons = filter_spec.get("seasons")
    if seasons and season is not None:
        if season.lower() not in [s.lower() for s in seasons]:
            return False

    owner, pooch_count, kennel_count = await _get_owner_counts(session, owner_discord_id)
    if owner is None:
        return False

    if filter_spec.get("min_money") is not None and owner.dollars < filter_spec["min_money"]:
        return False
    if filter_spec.get("max_money") is not None and owner.dollars > filter_spec["max_money"]:
        return False
    if _is_excluded(owner.dollars, filter_spec.get("exclude_money")):
        return False
    if filter_spec.get("min_bloodskulls") is not None and owner.bloodskulls < filter_spec["min_bloodskulls"]:
        return False
    if filter_spec.get("max_bloodskulls") is not None and owner.bloodskulls > filter_spec["max_bloodskulls"]:
        return False
    if _is_excluded(owner.bloodskulls, filter_spec.get("exclude_bloodskulls")):
        return False

    if filter_spec.get("min_pooches") is not None and pooch_count < filter_spec["min_pooches"]:
        return False
    if filter_spec.get("max_pooches") is not None and pooch_count > filter_spec["max_pooches"]:
        return False
    if _is_excluded(pooch_count, filter_spec.get("exclude_pooches")):
        return False
    if filter_spec.get("min_kennels") is not None and kennel_count < filter_spec["min_kennels"]:
        return False
    if filter_spec.get("max_kennels") is not None and kennel_count > filter_spec["max_kennels"]:
        return False
    if _is_excluded(kennel_count, filter_spec.get("exclude_kennels")):
        return False

    for kennel_filter in list(filter_spec.get("kennels", [])):
        min_count = kennel_filter.get("min_count", 1)
        max_count = kennel_filter.get("max_count")
        count = await count_matching_kennels_for_owner(
            session,
            owner_discord_id,
            _strip_requirement_metadata(kennel_filter),
        )
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    for pooch_filter in list(filter_spec.get("pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = await count_matching_pooches_for_owner(
            session,
            owner_discord_id,
            _strip_requirement_metadata(pooch_filter),
        )
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    for pooch_filter in list(filter_spec.get("graveyard_pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = await _count_graveyard_pooches_for_owner(session, owner_discord_id, pooch_filter)
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    for pooch_filter in list(filter_spec.get("hell_pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = await _count_hell_pooches_for_owner(session, owner_discord_id, pooch_filter)
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    return True


async def get_matching_stray_pooch_ids_for_server(
    session: AsyncSession,
    server_discord_id: int,
    filter_spec: "PoochFilterSpec | None",
) -> list[int]:
    """Return IDs of alive strays on the given server that match filter_spec."""
    query = await _build_pooch_query(session, dict(filter_spec) if filter_spec else {})
    stray_subquery = select(StrayPooch.pooch_id).where(StrayPooch.server_discord_id == server_discord_id)
    query = query.where(Pooch.id.in_(stray_subquery), Pooch.alive.is_(True))
    result = await session.execute(query.with_only_columns(Pooch.id))
    return list(result.scalars().all())


async def count_matching_stray_pooches_for_server(
    session: AsyncSession,
    server_discord_id: int,
    filter_spec: "PoochFilterSpec | None",
) -> int:
    ids = await get_matching_stray_pooch_ids_for_server(session, server_discord_id, filter_spec)
    return len(ids)


async def check_stray_event_filter(
    session: AsyncSession,
    server_discord_id: int,
    filter_spec: StrayEventFilterSpec | None,
    season: Optional[str] = None,
) -> bool:
    """Return True if the stray population on the server satisfies filter_spec."""

    if not filter_spec:
        # No filter — just need at least one alive stray
        stray_count = await session.scalar(
            select(func.count(StrayPooch.pooch_id))
            .join(Pooch, Pooch.id == StrayPooch.pooch_id)
            .where(StrayPooch.server_discord_id == server_discord_id, Pooch.alive.is_(True))
        )
        return (stray_count or 0) > 0

    seasons = filter_spec.get("seasons")
    if seasons and season is not None:
        if season.lower() not in [s.lower() for s in seasons]:
            return False

    for pooch_filter in list(filter_spec.get("pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = await count_matching_stray_pooches_for_server(
            session,
            server_discord_id,
            _strip_requirement_metadata(pooch_filter),
        )
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    return True


# ---------------------------------------------------------------------------
# Server-event eligibility filter
# ---------------------------------------------------------------------------


async def _count_dead_pooches_for_server(session: AsyncSession, server_discord_id: int) -> int:
    """Count pooches in the graveyard that belong to owners registered on this server."""
    from ..models import OwnerServer as OwnerServerModel

    count = await session.scalar(
        select(func.count(GraveyardPooch.pooch_id))
        .join(Pooch, Pooch.id == GraveyardPooch.pooch_id)
        .join(OwnerServerModel, OwnerServerModel.owner_discord_id == Pooch.owner_discord_id)
        .where(OwnerServerModel.server_discord_id == server_discord_id)
    )
    return count or 0


async def _count_hell_pooches_for_server(session: AsyncSession, server_discord_id: int) -> int:
    """Count pooches in hell that belong to owners registered on this server."""
    from ..models import OwnerServer as OwnerServerModel

    count = await session.scalar(
        select(func.count(HellPooch.pooch_id))
        .join(Pooch, Pooch.id == HellPooch.pooch_id)
        .join(OwnerServerModel, OwnerServerModel.owner_discord_id == Pooch.owner_discord_id)
        .where(OwnerServerModel.server_discord_id == server_discord_id)
    )
    return count or 0


async def _get_matching_dead_pooch_ids_for_server(
    session: AsyncSession, server_discord_id: int, filter_spec: "PoochFilterSpec | None"
) -> list[int]:
    from ..models import OwnerServer as OwnerServerModel

    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)

    owner_subquery = select(OwnerServerModel.owner_discord_id).where(
        OwnerServerModel.server_discord_id == server_discord_id
    )
    query = await _build_pooch_query(session, base_filter)
    graveyard_subquery = (
        select(GraveyardPooch.pooch_id)
        .join(Pooch, Pooch.id == GraveyardPooch.pooch_id)
        .where(Pooch.owner_discord_id.in_(owner_subquery))
    )
    query = query.where(Pooch.id.in_(graveyard_subquery))
    result = await session.execute(query.with_only_columns(Pooch.id))
    return list(result.scalars().all())


async def _get_matching_hell_pooch_ids_for_server(
    session: AsyncSession, server_discord_id: int, filter_spec: "PoochFilterSpec | None"
) -> list[int]:
    from ..models import OwnerServer as OwnerServerModel

    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)

    owner_subquery = select(OwnerServerModel.owner_discord_id).where(
        OwnerServerModel.server_discord_id == server_discord_id
    )
    query = await _build_pooch_query(session, base_filter)
    hell_subquery = (
        select(HellPooch.pooch_id)
        .join(Pooch, Pooch.id == HellPooch.pooch_id)
        .where(Pooch.owner_discord_id.in_(owner_subquery))
    )
    query = query.where(Pooch.id.in_(hell_subquery))
    result = await session.execute(query.with_only_columns(Pooch.id))
    return list(result.scalars().all())


async def get_matching_stray_pooch_ids_for_server_filtered(
    session: AsyncSession, server_discord_id: int, filter_spec: "PoochFilterSpec | None"
) -> list[int]:
    """Like get_matching_stray_pooch_ids_for_server but strips count metadata first."""
    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)
    return await get_matching_stray_pooch_ids_for_server(session, server_discord_id, base_filter)


async def check_server_event_filter(
    session: AsyncSession,
    server_discord_id: int,
    filter_spec: "ServerEventFilterSpec | None",
    season: Optional[str] = None,
) -> bool:
    """Return True if the given server satisfies the server event eligibility filter."""
    from ..models import OwnerServer as OwnerServerModel

    if not filter_spec:
        return True

    seasons = filter_spec.get("seasons")
    if seasons and season is not None:
        if season.lower() not in [s.lower() for s in seasons]:
            return False

    # Owner count
    owner_count = (
        await session.scalar(
            select(func.count(OwnerServerModel.owner_discord_id)).where(
                OwnerServerModel.server_discord_id == server_discord_id
            )
        )
        or 0
    )
    if filter_spec.get("min_owners") is not None and owner_count < filter_spec["min_owners"]:
        return False
    if filter_spec.get("max_owners") is not None and owner_count > filter_spec["max_owners"]:
        return False

    # Stray count
    if filter_spec.get("min_strays") is not None or filter_spec.get("max_strays") is not None:
        stray_count = (
            await session.scalar(
                select(func.count(StrayPooch.pooch_id))
                .join(Pooch, Pooch.id == StrayPooch.pooch_id)
                .where(StrayPooch.server_discord_id == server_discord_id, Pooch.alive.is_(True))
            )
            or 0
        )
        if filter_spec.get("min_strays") is not None and stray_count < filter_spec["min_strays"]:
            return False
        if filter_spec.get("max_strays") is not None and stray_count > filter_spec["max_strays"]:
            return False

    # Dead count
    if filter_spec.get("min_dead") is not None or filter_spec.get("max_dead") is not None:
        dead_count = await _count_dead_pooches_for_server(session, server_discord_id)
        if filter_spec.get("min_dead") is not None and dead_count < filter_spec["min_dead"]:
            return False
        if filter_spec.get("max_dead") is not None and dead_count > filter_spec["max_dead"]:
            return False

    # Hell count
    if filter_spec.get("min_in_hell") is not None or filter_spec.get("max_in_hell") is not None:
        hell_count = await _count_hell_pooches_for_server(session, server_discord_id)
        if filter_spec.get("min_in_hell") is not None and hell_count < filter_spec["min_in_hell"]:
            return False
        if filter_spec.get("max_in_hell") is not None and hell_count > filter_spec["max_in_hell"]:
            return False

    # Stray pooch sub-filters
    for pooch_filter in list(filter_spec.get("stray_pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = len(await get_matching_stray_pooch_ids_for_server_filtered(session, server_discord_id, pooch_filter))
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    # Dead pooch sub-filters
    for pooch_filter in list(filter_spec.get("dead_pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = len(await _get_matching_dead_pooch_ids_for_server(session, server_discord_id, pooch_filter))
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    # Hell pooch sub-filters
    for pooch_filter in list(filter_spec.get("hell_pooches", [])):
        min_count = pooch_filter.get("min_count", 1)
        max_count = pooch_filter.get("max_count")
        count = len(await _get_matching_hell_pooch_ids_for_server(session, server_discord_id, pooch_filter))
        if count < min_count:
            return False
        if max_count is not None and count > max_count:
            return False

    # Per-owner sub-filters
    for owner_filter in list(filter_spec.get("owners", [])):
        min_count = owner_filter.get("min_count", 1)
        max_count = owner_filter.get("max_count")
        # Get all owner IDs registered in this server
        owner_ids_result = await session.execute(
            select(OwnerServerModel.owner_discord_id).where(OwnerServerModel.server_discord_id == server_discord_id)
        )
        all_owner_ids = list(owner_ids_result.scalars().all())
        # Count how many of them satisfy the owner filter (minus count metadata)
        stripped_filter = {k: v for k, v in owner_filter.items() if k not in {"min_count", "max_count"}}
        matching = 0
        for oid in all_owner_ids:
            if await check_owner_event_filter(session, oid, stripped_filter):
                matching += 1
        if matching < min_count:
            return False
        if max_count is not None and matching > max_count:
            return False

    return True
