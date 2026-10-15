import random
from typing import Optional

from sqlalchemy import and_, func, literal, not_, or_, select, true, union
from sqlalchemy.orm import aliased, selectinload

from .models import (
    AuctionBid,
    AuctionBountyListing,
    AuctionSaleListing,
    Breed,
    Disease,
    Event,
    EventOccurrence,
    EventOption,
    EventOutcome,
    GlobalState,
    HealthImpactWeight,
    Injury,
    Item,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    OwnerItem,
    OwnerServer,
    Pooch,
    PoochBreed,
    PoochDisease,
    PoochInjury,
    PoochMutation,
    PoochParentage,
    Server,
    ServerEvent,
    ServerEventMenu,
    ServerEventMenuOption,
    ServerEventOccurrence,
    ServerEventOutcome,
    ServerEventParticipation,
    StrayEvent,
    StrayEventOutcome,
    Vendor,
)
from .session import session_scope
from .utils import check_owner_event_filter, check_server_event_filter, rarity_choice


async def get_active_owner_event_by_id(active_owner_event_id: int) -> Optional[EventOccurrence]:
    """
    Get an active event by its ID.

    Parameters
    ----------
    active_owner_event_id: int
        The ID of the active event to retrieve.

    Returns
    -------
    EventOccurrence, optional
        The EventOccurrence ORM object with the given ID, or None if it doesn't exist.
    """

    async with session_scope() as session:
        query = (
            select(EventOccurrence)
            .where(EventOccurrence.id == active_owner_event_id, EventOccurrence.archived.is_(False))
            .options(
                selectinload(EventOccurrence.event).selectinload(Event.actions),
                selectinload(EventOccurrence.event).selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(EventOccurrence.event)
                .selectinload(Event.options)
                .selectinload(EventOption.outcomes)
                .selectinload(EventOutcome.actions),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_breed_by_id(breed_id: int) -> Optional[Breed]:
    """
    Fetch a breed by its ID.

    Parameters
    ----------
    breed_id: int
        The ID of the breed to fetch.

    Returns
    -------
    Breed, optional
        The Breed ORM object, or None if no breed with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Breed).where(Breed.id == breed_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_breed_by_name(name: str) -> Optional[Breed]:
    """
    Fetch a breed by its name (case-insensitive).

    Parameters
    ----------
    name: str
        The name of the breed to fetch.

    Returns
    -------
    Breed, optional
        The Breed ORM object, or None if no breed with the given name exists.
    """

    async with session_scope() as session:
        query = select(Breed).where(Breed.name.ilike(name))
        response = await session.execute(query)

    return response.scalar_one_or_none()


def _breed_allowed_in_season(breed: "Breed", season: str) -> bool:
    """Return True if the breed is available in the given season (already lowercased)."""
    seasons = breed.parameters.get("seasons") if breed.parameters else None
    if seasons is None:
        return True
    return season in [s.lower() for s in seasons]


def _mutation_allowed_in_season(mutation: "Mutation", season: str) -> bool:
    """Return True if the mutation is available in the given season (already lowercased)."""
    seasons = mutation.parameters.get("seasons") if mutation.parameters else None
    if seasons is None:
        return True
    return season in [s.lower() for s in seasons]


async def get_random_breed_ids(
    n: int,
    rng: Optional[random.Random] = None,
    from_vendor: bool = False,
    from_ritual: bool = False,
    exclude_ids: Optional[list[int]] = None,
    season: Optional[str] = None,
) -> list[int]:
    """
    Return a list of `n` randomly-selected breed IDs, weighted by rarity.
    Sampling is done with replacement, so the same breed can appear more than once.

    Parameters
    ----------
    n: int
        How many breed IDs to return.

    rng: Random, optional
        The random generator to use. A fresh one is created if not given.

    from_vendor: bool, default : False
        When True, exclude breeds whose parameters contain ``{"sold_by_vendors": False}``.

    from_ritual: bool, default : False
        When True, exclude breeds whose parameters contain ``{"born_from_ritual": False}``.

    season: str, optional
        When provided, exclude breeds whose ``parameters.seasons`` list does not include
        this season (case-insensitive). Breeds with no ``seasons`` key are always eligible.

    Returns
    -------
    list[int]
        A list of `n` breed IDs (with possible duplicates). Empty if no eligible
        breeds exist in the database.
    """

    rng = rng if rng is not None else random.Random()
    result: list[int] = []
    if n <= 0:
        return result

    async with session_scope() as session:
        query = select(Breed)
        if from_vendor:
            query = query.where(not_(Breed.parameters.contains({"sold_by_vendors": False})))
        if from_ritual:
            query = query.where(not_(Breed.parameters.contains({"born_from_ritual": False})))
        if exclude_ids:
            query = query.where(Breed.id.not_in(exclude_ids))
        response = await session.execute(query)
        raw_rows = response.scalars().all()

    if season is not None:
        season_lower = season.lower()
        rows = [(breed, breed.rarity) for breed in raw_rows if _breed_allowed_in_season(breed, season_lower)]
    else:
        rows = [(breed, breed.rarity) for breed in raw_rows]

    if not rows:
        return result

    for _ in range(n):
        breed = rarity_choice(rng, rows)
        if breed is not None:
            result.append(breed.id)

    return result


async def get_owner_event_by_id(event_id: int) -> Optional[Event]:
    """
    Get an event by its ID.

    Parameters
    ----------
    event_id: int
        The ID of the event to retrieve.

    Returns
    -------
    Event, optional
        The Event ORM object with the given ID, or None if it doesn't exist.
    """

    async with session_scope() as session:
        query = (
            select(Event)
            .where(Event.id == event_id)
            .options(
                selectinload(Event.actions),
                selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(Event.options).selectinload(EventOption.outcomes).selectinload(EventOutcome.actions),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_event_by_name(event_name: str) -> Optional[Event]:
    """
    Fetch an event by its name.

    Parameters
    ----------
    event_name: str
        The name of the event to fetch.

    Returns
    -------
    Event, optional
        The ORM event object if found, otherwise None.
    """

    async with session_scope() as session:
        query = (
            select(Event)
            .where(Event.name == event_name)
            .options(
                selectinload(Event.actions),
                selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(Event.options).selectinload(EventOption.outcomes).selectinload(EventOutcome.actions),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_event_option_by_id(option_id: int) -> Optional[EventOption]:
    """
    Get an event option by its ID.

    Parameters
    ----------
    option_id: int
        The ID of the event option to retrieve.

    Returns
    -------
    EventOption, optional
        The EventOption ORM object with the given ID, or None if it doesn't exist.
    """

    async with session_scope() as session:
        query = (
            select(EventOption)
            .where(EventOption.id == option_id)
            .options(
                selectinload(EventOption.actions),
                selectinload(EventOption.outcomes).selectinload(EventOutcome.actions),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


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


async def get_mutation_by_id(mutation_id: int) -> Optional[Mutation]:
    """
    Fetch a mutation by its ID.

    Parameters
    ----------
    mutation_id: int
        The ID of the mutation to fetch.

    Returns
    -------
    Mutation, optional
        The Mutation ORM object, or None if no mutation with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Mutation).where(Mutation.id == mutation_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_mutation_by_name(name: str) -> Optional[Mutation]:
    """Fetch a mutation by its name (case-insensitive)."""
    async with session_scope() as session:
        query = select(Mutation).where(Mutation.name.ilike(name))
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_injury_by_id(injury_id: int) -> Optional[Injury]:
    """Fetch an injury by its ID."""
    async with session_scope() as session:
        return await session.get(Injury, injury_id)


async def get_injury_by_name(name: str) -> Optional[Injury]:
    """Fetch an injury by its name (case-insensitive)."""
    async with session_scope() as session:
        query = select(Injury).where(Injury.name.ilike(name))
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_random_injury(
    rng: random.Random,
    min_severity: Optional[str] = None,
    max_severity: Optional[str] = None,
    min_health_impact: Optional[str] = None,
    max_health_impact: Optional[str] = None,
) -> Optional[Injury]:
    """
    Return a random Injury, optionally filtered by severity and/or health_impact range.

    Severity order: trivial < minor < moderate < major < critical < remarkable < catastrophic
    Health impact order follows HealthImpactWeight ordering (lower weight = more harmful).
    """
    _SEVERITY_ORDER = ["trivial", "minor", "moderate", "major", "critical", "remarkable", "catastrophic"]

    async with session_scope() as session:
        query = select(Injury)

        if min_severity is not None or max_severity is not None:
            sev_min_idx = _SEVERITY_ORDER.index(min_severity) if min_severity else 0
            sev_max_idx = _SEVERITY_ORDER.index(max_severity) if max_severity else len(_SEVERITY_ORDER) - 1
            allowed_severities = _SEVERITY_ORDER[sev_min_idx : sev_max_idx + 1]
            query = query.where(Injury.severity.in_(allowed_severities))

        if min_health_impact is not None or max_health_impact is not None:
            # Join to HealthImpactWeight to filter by numeric range
            hi_subq_min = (
                (
                    select(HealthImpactWeight.weight).where(HealthImpactWeight.health_impact == min_health_impact)
                ).scalar_subquery()
                if min_health_impact
                else None
            )
            hi_subq_max = (
                (
                    select(HealthImpactWeight.weight).where(HealthImpactWeight.health_impact == max_health_impact)
                ).scalar_subquery()
                if max_health_impact
                else None
            )
            query = query.join(HealthImpactWeight, HealthImpactWeight.health_impact == Injury.health_impact)
            if hi_subq_min is not None:
                query = query.where(HealthImpactWeight.weight >= hi_subq_min)
            if hi_subq_max is not None:
                query = query.where(HealthImpactWeight.weight <= hi_subq_max)

        injuries = list((await session.execute(query)).scalars().all())

    if not injuries:
        return None
    return rng.choice(injuries)


async def get_injury_health_impact(injury_id: int) -> Optional[int]:
    """
    Get the health impact for the injury with the given ID as an integer.

    Parameters
    ----------
    injury_id: int
        The ID of the injury to get the numerical health impact of.

    Returns
    -------
    int, optional
        The health impact of the given injury, or None if the injury wasn't found.
    """

    async with session_scope() as session:
        query = (
            select(HealthImpactWeight.weight)
            .join(Injury, Injury.health_impact == HealthImpactWeight.health_impact)
            .where(Injury.id == injury_id)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_mutation_health_impact(mutation_id: int) -> Optional[int]:
    """
    Get the health impact for the mutation with the given ID as an integer.

    Parameters
    ----------
    mutation_id: int
        The ID of the mutation to get the numerical health impact of.

    Returns
    -------
    int, optional
        The health impact of the given mutation, or None if the mutation wasn't found.
    """

    async with session_scope() as session:
        query = (
            select(HealthImpactWeight.weight)
            .join(Mutation, Mutation.health_impact == HealthImpactWeight.health_impact)
            .where(Mutation.id == mutation_id)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_by_discord_id(owner_discord_id: int) -> Optional[Owner]:
    """
    Fetch an owner by their Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch.

    Returns
    -------
    Owner, optional
        The Owner ORM object, or None if no owner with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_server(server_discord_id: int, owner_discord_id: int) -> Optional[OwnerServer]:
    """
    Get the owner-server relationship with the given server and owner Discord IDs.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server in the owner-server relationship.

    owner_discord_id: int
        The Discord ID of the owner in the owner-server relationship.

    Returns
    -------
    OwnerServer, optional
        The OwnerServer ORM relationship object with the given ID pair, or None if it doesn't exist.
    """

    async with session_scope() as session:
        query = select(OwnerServer).where(
            and_(OwnerServer.server_discord_id == server_discord_id, OwnerServer.owner_discord_id == owner_discord_id)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_pending_active_owner_event(
    owner_discord_id: int, event_id: Optional[int] = None
) -> Optional[EventOccurrence]:
    """
    Get a pending (unresponded) active event for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    event_id: int, optional
        The specific event ID to look for. If None, returns any pending event.

    Returns
    -------
    EventOccurrence, optional
        The pending EventOccurrence, or None if no pending event exists.
    """

    async with session_scope() as session:
        conditions = [
            EventOccurrence.owner_discord_id == owner_discord_id,
            EventOccurrence.archived.is_(False),
            EventOccurrence.responded_at.is_(None),
        ]
        if event_id is not None:
            conditions.append(EventOccurrence.event_id == event_id)

        query = (
            select(EventOccurrence)
            .where(and_(*conditions))
            .options(
                selectinload(EventOccurrence.event).selectinload(Event.actions),
                selectinload(EventOccurrence.event).selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(EventOccurrence.event)
                .selectinload(Event.options)
                .selectinload(EventOption.outcomes)
                .selectinload(EventOutcome.actions),
            )
            .order_by(EventOccurrence.triggered_at.desc())
            .limit(1)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


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


async def get_pooch_health_impact(pooch_id: int) -> int:
    """
    Return the summed health-impact weight of all of a pooch's mutations, injuries and diseases.

    The game layer adds this to the pooch's effective base health (see ``game.manage_stats.get_pooch_health``).
    """

    async with session_scope() as session:
        InjuryWeight = aliased(HealthImpactWeight)
        DiseaseWeight = aliased(HealthImpactWeight)

        injury_subq = (
            select(func.coalesce(func.sum(InjuryWeight.weight), 0))
            .select_from(PoochInjury)
            .join(Injury, Injury.id == PoochInjury.injury_id)
            .join(InjuryWeight, InjuryWeight.health_impact == Injury.health_impact)
            .where(PoochInjury.pooch_id == pooch_id)
            .scalar_subquery()
        )
        disease_subq = (
            select(func.coalesce(func.sum(DiseaseWeight.weight), 0))
            .select_from(PoochDisease)
            .join(Disease, Disease.id == PoochDisease.disease_id)
            .join(DiseaseWeight, DiseaseWeight.health_impact == Disease.health_impact)
            .where(PoochDisease.pooch_id == pooch_id)
            .scalar_subquery()
        )
        mutation_subq = (
            select(func.coalesce(func.sum(HealthImpactWeight.weight), 0))
            .select_from(PoochMutation)
            .join(Mutation, Mutation.id == PoochMutation.mutation_id)
            .join(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(PoochMutation.pooch_id == pooch_id)
            .scalar_subquery()
        )
        total_impact = await session.scalar(select(mutation_subq + injury_subq + disease_subq))
    return int(total_impact or 0)


async def get_pooch_stat_sources(
    pooch_id: int,
) -> Optional[tuple[Pooch, list[PoochMutation], list[tuple[Breed, float]], list[PoochInjury], list[PoochDisease]]]:
    """
    Return everything that affects a pooch's stats, in one session: the pooch, its mutation instances, its breeds
    with their weights, and its injury and disease instances (each with its catalog row loaded).

    Returns None if the pooch doesn't exist. The math lives in ``game.manage_stats``.
    """

    async with session_scope() as session:
        pooch = await session.scalar(select(Pooch).where(Pooch.id == pooch_id))
        if pooch is None:
            return None
        mutations = (
            (
                await session.execute(
                    select(PoochMutation)
                    .options(selectinload(PoochMutation.mutation))
                    .where(PoochMutation.pooch_id == pooch_id)
                )
            )
            .scalars()
            .all()
        )
        breed_rows = (
            await session.execute(
                select(Breed, PoochBreed.weight)
                .join(PoochBreed, PoochBreed.breed_id == Breed.id)
                .where(PoochBreed.pooch_id == pooch_id)
            )
        ).all()
        injuries = (
            (
                await session.execute(
                    select(PoochInjury)
                    .options(selectinload(PoochInjury.injury))
                    .where(PoochInjury.pooch_id == pooch_id)
                )
            )
            .scalars()
            .all()
        )
        diseases = (
            (
                await session.execute(
                    select(PoochDisease)
                    .options(selectinload(PoochDisease.disease))
                    .where(PoochDisease.pooch_id == pooch_id)
                )
            )
            .scalars()
            .all()
        )
    return pooch, list(mutations), [(breed, weight) for breed, weight in breed_rows], list(injuries), list(diseases)


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

    # Guard against asexual-reproduction rows where father_id == mother_id
    if parentage.father_id is not None and parentage.father_id == parentage.mother_id:
        father = None

    return (father, mother)


async def get_pooch_virginity_status(pooch_id: int) -> Optional[bool]:
    """
    Get whether the pooch with the given ID is a virgin or not.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the virginity status of.

    Returns
    -------
    bool, optional
        Whether the pooch is a virgin or not, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch.virgin).where(Pooch.id == pooch_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_random_eligible_owner_event_for_owner(
    owner_discord_id: int,
    rng: Optional[random.Random] = None,
    include_triggered_only: bool = False,
    season: Optional[str] = None,
) -> Optional[Event]:
    """
    Get a random eligible event for an owner, weighted by rarity.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    rng: Random, optional
        The random generator to use for weighted selection.

    include_triggered_only: bool, default : False
        Whether to include events marked as being triggered only be other events or not.

    Returns
    -------
    Event, optional
        A randomly selected Event ORM object, or None if no eligible events exist.
    """

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:
        owner = await session.scalar(select(Owner).where(Owner.discord_id == owner_discord_id))
        if owner is None:
            return None

        event_query = (
            select(Event)
            .where(
                true() if include_triggered_only else Event.triggered_only.is_(False),
            )
            .options(
                selectinload(Event.actions),
                selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(Event.options).selectinload(EventOption.outcomes).selectinload(EventOutcome.actions),
            )
        )
        event_response = await session.execute(event_query)
        rows = event_response.scalars().all()

        if not rows:
            return None

        eligible_rows: list[tuple[Event, str]] = []
        for event in rows:
            if await check_owner_event_filter(session, owner_discord_id, event.filter, season=season):
                eligible_rows.append((event, event.rarity))

        if not eligible_rows:
            return None

        return rarity_choice(rng, eligible_rows)


async def check_owner_event_filter_for_owner(owner_discord_id: int, filter_spec: dict | None) -> bool:
    """
    Check owner event filter for owner.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    filter_spec: Any
        The `filter_spec` value.

    Returns
    -------
    Any
        The result of calling `check_owner_event_filter_for_owner`.
    """

    async with session_scope() as session:
        return await check_owner_event_filter(session, owner_discord_id, filter_spec or {})


async def check_server_event_filter_for_server(
    server_discord_id: int, filter_spec: dict | None, season: str | None = None
) -> bool:
    """Session-free wrapper around check_server_event_filter."""
    async with session_scope() as session:
        return await check_server_event_filter(session, server_discord_id, filter_spec or {}, season=season)


async def get_random_matching_pooch_id(
    owner_discord_id: int,
    filter_spec: dict | None,
    rng: random.Random,
) -> Optional[int]:
    """
    Get random matching pooch id.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    filter_spec: Any
        The `filter_spec` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `get_random_matching_pooch_id`.
    """

    from .utils import get_random_matching_pooch_id_for_owner

    async with session_scope() as session:
        return await get_random_matching_pooch_id_for_owner(session, owner_discord_id, filter_spec or {}, rng)


async def get_random_matching_kennel_id(
    owner_discord_id: int,
    filter_spec: dict | None,
    rng: random.Random,
) -> Optional[int]:
    """
    Get random matching kennel id.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    filter_spec: Any
        The `filter_spec` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `get_random_matching_kennel_id`.
    """

    from .utils import get_random_matching_kennel_id_for_owner

    async with session_scope() as session:
        return await get_random_matching_kennel_id_for_owner(session, owner_discord_id, filter_spec or {}, rng)


async def get_server_by_discord_id(server_discord_id: int) -> Optional[Server]:
    """
    Fetch a server by its Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to fetch.

    Returns
    -------
    Server, optional
        The Server ORM object, or None if no server with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Server).where(Server.discord_id == server_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


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


async def get_vendor_server(vendor_id: int) -> Optional[Server]:
    """
    Get the server the vendor with the given ID belongs to.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to get the server for.

    Returns
    -------
    Server, optional
        The Server ORM object representing the server the vendor belongs to.
    """

    async with session_scope() as session:
        query = select(Server).join(Vendor, Vendor.server_discord_id == Server.discord_id).where(Vendor.id == vendor_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


def _server_event_load_options():
    return [
        selectinload(ServerEvent.actions),
        selectinload(ServerEvent.menus)
        .selectinload(ServerEventMenu.options)
        .selectinload(ServerEventMenuOption.actions),
        selectinload(ServerEvent.outcomes).selectinload(ServerEventOutcome.actions),
    ]


async def get_server_event_by_id(server_event_id: int) -> Optional[ServerEvent]:
    """
    Get server event by id.

    Parameters
    ----------
    server_event_id: Any
        The `server_event_id` value.

    Returns
    -------
    Any
        The result of calling `get_server_event_by_id`.
    """

    async with session_scope() as session:
        query = select(ServerEvent).where(ServerEvent.id == server_event_id).options(*_server_event_load_options())
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_server_event_menu_option_by_id(option_id: int) -> Optional[ServerEventMenuOption]:
    """
    Get server event menu option by id.

    Parameters
    ----------
    option_id: Any
        The `option_id` value.

    Returns
    -------
    Any
        The result of calling `get_server_event_menu_option_by_id`.
    """

    async with session_scope() as session:
        query = (
            select(ServerEventMenuOption)
            .where(ServerEventMenuOption.id == option_id)
            .options(
                selectinload(ServerEventMenuOption.actions),
                selectinload(ServerEventMenuOption.menu),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_server_event_occurrence_by_id(occurrence_id: int) -> Optional[ServerEventOccurrence]:
    """
    Get server event occurrence by id.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    Returns
    -------
    Any
        The result of calling `get_server_event_occurrence_by_id`.
    """

    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .where(ServerEventOccurrence.id == occurrence_id)
            .options(
                selectinload(ServerEventOccurrence.server_event).options(*_server_event_load_options()),
                selectinload(ServerEventOccurrence.participations),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_active_server_event_occurrence(server_discord_id: int) -> Optional[ServerEventOccurrence]:
    """
    Get active server event occurrence.

    Parameters
    ----------
    server_discord_id: Any
        The `server_discord_id` value.

    Returns
    -------
    Any
        The result of calling `get_active_server_event_occurrence`.
    """

    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .where(
                ServerEventOccurrence.server_discord_id == server_discord_id,
                ServerEventOccurrence.archived.is_(False),
                ServerEventOccurrence.resolved_at.is_(None),
            )
            .options(
                selectinload(ServerEventOccurrence.server_event).options(*_server_event_load_options()),
                selectinload(ServerEventOccurrence.participations),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_active_server_event_occurrence_by_tier(
    server_discord_id: int, tier: str
) -> Optional[ServerEventOccurrence]:
    """Return the active (unresolved, unarchived) server event occurrence for the given tier, or None."""
    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .join(ServerEvent, ServerEventOccurrence.server_event_id == ServerEvent.id)
            .where(
                ServerEventOccurrence.server_discord_id == server_discord_id,
                ServerEventOccurrence.archived.is_(False),
                ServerEventOccurrence.resolved_at.is_(None),
                ServerEvent.tier == tier.strip().lower(),
            )
            .options(
                selectinload(ServerEventOccurrence.server_event).options(*_server_event_load_options()),
                selectinload(ServerEventOccurrence.participations),
            )
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_server_event_participation(
    occurrence_id: int, owner_discord_id: int
) -> Optional[ServerEventParticipation]:
    """
    Get server event participation.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    owner_discord_id: Any
        The `owner_discord_id` value.

    Returns
    -------
    Any
        The result of calling `get_server_event_participation`.
    """

    async with session_scope() as session:
        query = select(ServerEventParticipation).where(
            ServerEventParticipation.occurrence_id == occurrence_id,
            ServerEventParticipation.owner_discord_id == owner_discord_id,
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def list_all_server_events_with_weights() -> list[tuple[ServerEvent, str]]:
    """Return all server events paired with their rarity string, fully loaded."""
    async with session_scope() as session:
        event_query = select(ServerEvent).options(*_server_event_load_options())
        response = await session.execute(event_query)
        return [(event, event.rarity) for event in response.scalars().all()]


async def get_server_event_by_name(name: str) -> Optional[ServerEvent]:
    """Return a fully-loaded ServerEvent by its unique name, or None."""
    async with session_scope() as session:
        result = await session.execute(
            select(ServerEvent).where(ServerEvent.name == name).options(*_server_event_load_options())
        )
        return result.scalars().first()


async def list_server_events_with_weights_by_tier(tier: str) -> list[tuple[ServerEvent, str]]:
    """Return server events for a specific tier ('minor' or 'major') with their rarity string."""
    async with session_scope() as session:
        event_query = select(ServerEvent).where(ServerEvent.tier == tier.lower()).options(*_server_event_load_options())
        response = await session.execute(event_query)
        return [(event, event.rarity) for event in response.scalars().all()]


def _stray_event_load_options():
    return [
        selectinload(StrayEvent.actions),
        selectinload(StrayEvent.outcomes).selectinload(StrayEventOutcome.actions),
    ]


async def get_stray_event_by_id(stray_event_id: int) -> Optional[StrayEvent]:
    """
    Get stray event by id.

    Parameters
    ----------
    stray_event_id: Any
        The `stray_event_id` value.

    Returns
    -------
    Any
        The result of calling `get_stray_event_by_id`.
    """

    async with session_scope() as session:
        query = select(StrayEvent).where(StrayEvent.id == stray_event_id).options(*_stray_event_load_options())
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_stray_event_by_name(name: str) -> Optional[StrayEvent]:
    """
    Get stray event by name.

    Parameters
    ----------
    name: Any
        The `name` value.

    Returns
    -------
    Any
        The result of calling `get_stray_event_by_name`.
    """

    async with session_scope() as session:
        query = select(StrayEvent).where(StrayEvent.name == name).options(*_stray_event_load_options())
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_random_eligible_stray_event_for_server(
    server_discord_id: int,
    rng: Optional[random.Random] = None,
    include_triggered_only: bool = False,
    season: Optional[str] = None,
) -> Optional[StrayEvent]:
    """
    Pick a random stray event weighted by rarity, from those whose top-level filter is satisfied
    by the current stray population of the given server.
    """
    from .utils import check_stray_event_filter

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:
        query = (
            select(StrayEvent)
            .where(
                true() if include_triggered_only else StrayEvent.triggered_only.is_(False),
            )
            .options(*_stray_event_load_options())
        )
        response = await session.execute(query)
        rows = response.scalars().all()

        if not rows:
            return None

        eligible_rows: list[tuple[StrayEvent, str]] = []
        for event in rows:
            if await check_stray_event_filter(session, server_discord_id, event.filter, season=season):
                eligible_rows.append((event, event.rarity))

        if not eligible_rows:
            return None

        return rarity_choice(rng, eligible_rows)


async def get_parentage_maps(
    root_id: int,
    ancestor_depth: int,
    descendant_depth: int,
) -> tuple[dict[int, tuple[int | None, int | None]], dict[int, list[int]]]:
    """
    Load parentage rows reachable from *root_id* within the given depth limits
    using recursive CTEs (1 query).

    Parameters
    ----------
    root_id: int
        The ID of the root pooch to start traversal from.
    ancestor_depth: int
        How many generations upward to traverse.
    descendant_depth: int
        How many generations downward to traverse.

    Returns
    -------
    tuple[dict, dict]
        (parents_of, children_of) where:
        parents_of[child_id] = (father_id, mother_id)
        children_of[parent_id] = [child_id, ...]
    """
    # Ancestor recursive CTE
    ancestor_base = select(
        PoochParentage.child_id,
        PoochParentage.father_id,
        PoochParentage.mother_id,
        literal(0).label("depth"),
    ).where(PoochParentage.child_id == root_id)
    ancestor_cte = ancestor_base.cte("ancestor_rows", recursive=True)

    ancestor_recursive = (
        select(
            PoochParentage.child_id,
            PoochParentage.father_id,
            PoochParentage.mother_id,
            (ancestor_cte.c.depth + 1).label("depth"),
        )
        .join(
            ancestor_cte,
            or_(
                PoochParentage.child_id == ancestor_cte.c.father_id,
                PoochParentage.child_id == ancestor_cte.c.mother_id,
            ),
        )
        .where(ancestor_cte.c.depth < ancestor_depth)
    )
    ancestor_cte = ancestor_cte.union_all(ancestor_recursive)

    # Descendant recursive CTE
    descendant_base = select(
        PoochParentage.child_id,
        PoochParentage.father_id,
        PoochParentage.mother_id,
        literal(1).label("depth"),
    ).where(
        or_(
            PoochParentage.father_id == root_id,
            PoochParentage.mother_id == root_id,
        )
    )
    descendant_cte = descendant_base.cte("descendant_rows", recursive=True)

    descendant_recursive = (
        select(
            PoochParentage.child_id,
            PoochParentage.father_id,
            PoochParentage.mother_id,
            (descendant_cte.c.depth + 1).label("depth"),
        )
        .join(
            descendant_cte,
            or_(
                PoochParentage.father_id == descendant_cte.c.child_id,
                PoochParentage.mother_id == descendant_cte.c.child_id,
            ),
        )
        .where(descendant_cte.c.depth < descendant_depth)
    )
    descendant_cte = descendant_cte.union_all(descendant_recursive)

    # Sibling query: rows sharing the same parents as root
    PP2 = PoochParentage.__table__.alias("sibling_pp")
    sibling_query = select(
        PP2.c.child_id,
        PP2.c.father_id,
        PP2.c.mother_id,
    ).where(
        PP2.c.father_id
        == select(PoochParentage.father_id).where(PoochParentage.child_id == root_id).correlate(None).scalar_subquery(),
        PP2.c.mother_id
        == select(PoochParentage.mother_id).where(PoochParentage.child_id == root_id).correlate(None).scalar_subquery(),
    )

    # Combine all three into a single query
    combined = union(
        select(
            ancestor_cte.c.child_id,
            ancestor_cte.c.father_id,
            ancestor_cte.c.mother_id,
        ),
        select(
            descendant_cte.c.child_id,
            descendant_cte.c.father_id,
            descendant_cte.c.mother_id,
        ),
        sibling_query,
    )

    parents_of: dict[int, tuple[int | None, int | None]] = {}
    children_of: dict[int, list[int]] = {}

    async with session_scope() as session:
        result = await session.execute(combined)
        rows = result.all()

    for row in rows:
        cid, fid, mid = row[0], row[1], row[2]
        parents_of[cid] = (fid, mid)
        if fid is not None:
            children_of.setdefault(fid, []).append(cid)
        if mid is not None:
            children_of.setdefault(mid, []).append(cid)

    for kids in children_of.values():
        kids.sort()

    return parents_of, children_of


async def get_auction_sale_listing_by_id(listing_id: int) -> Optional[AuctionSaleListing]:
    """Fetch a sale listing by primary key, regardless of active status."""
    async with session_scope() as session:
        return await session.get(AuctionSaleListing, listing_id)


async def get_active_auction_sale_listing_for_pooch(pooch_id: int) -> Optional[AuctionSaleListing]:
    """Return the active listing for a pooch, or None if not listed."""
    async with session_scope() as session:
        query = select(AuctionSaleListing).where(
            AuctionSaleListing.pooch_id == pooch_id,
            AuctionSaleListing.is_active.is_(True),
        )
        return (await session.execute(query)).scalar_one_or_none()


async def get_auction_bounty_listing_by_id(listing_id: int) -> Optional[AuctionBountyListing]:
    """Fetch a bounty listing by primary key, regardless of active status."""
    async with session_scope() as session:
        return await session.get(AuctionBountyListing, listing_id)


async def get_highest_bid_for_listing(listing_id: int) -> Optional[AuctionBid]:
    """Return the bid with the highest amount for the listing, or None if no bids."""
    async with session_scope() as session:
        query = (
            select(AuctionBid).where(AuctionBid.listing_id == listing_id).order_by(AuctionBid.amount.desc()).limit(1)
        )
        return (await session.execute(query)).scalar_one_or_none()


async def get_disease_by_id(disease_id: int) -> Optional[Disease]:
    """Fetch a disease by its ID."""
    async with session_scope() as session:
        return await session.get(Disease, disease_id)


async def get_disease_by_name(name: str) -> Optional[Disease]:
    """Fetch a disease by its name (case-insensitive)."""
    async with session_scope() as session:
        query = select(Disease).where(Disease.name.ilike(name))
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_disease_health_impact(disease_id: int) -> Optional[int]:
    """
    Get the health impact for the disease with the given ID as an integer.

    Parameters
    ----------
    disease_id: int
        The ID of the disease to get the numerical health impact of.

    Returns
    -------
    int, optional
        The health impact of the given disease, or None if the disease wasn't found.
    """

    async with session_scope() as session:
        query = (
            select(HealthImpactWeight.weight)
            .join(Disease, Disease.health_impact == HealthImpactWeight.health_impact)
            .where(Disease.id == disease_id)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_pooch_injury_instance(pooch_injury_id: int) -> Optional[PoochInjury]:
    """Fetch a PoochInjury join record by ID, with its injury and pooch relationships eagerly loaded."""
    async with session_scope() as session:
        query = (
            select(PoochInjury)
            .options(selectinload(PoochInjury.injury), selectinload(PoochInjury.pooch))
            .where(PoochInjury.id == pooch_injury_id)
        )
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_pooch_disease_instance(pooch_disease_id: int) -> Optional[PoochDisease]:
    """Fetch a PoochDisease join record by ID, with its disease and pooch relationships eagerly loaded."""
    async with session_scope() as session:
        query = (
            select(PoochDisease)
            .options(selectinload(PoochDisease.disease), selectinload(PoochDisease.pooch))
            .where(PoochDisease.id == pooch_disease_id)
        )
        response = await session.execute(query)
    return response.scalar_one_or_none()


_GET_GLOBAL_STATE_ID = 1


async def get_current_day() -> int:
    """Return the current global day number, defaulting to 0 if the row doesn't exist yet."""
    async with session_scope() as session:
        row = await session.get(GlobalState, _GET_GLOBAL_STATE_ID)
        if row is None:
            return 0
        return row.current_day


async def get_current_hour() -> int:
    """Return the current global hour number, defaulting to 0."""
    async with session_scope() as session:
        row = await session.get(GlobalState, _GET_GLOBAL_STATE_ID)
        if row is None:
            return 0
        return int(row.current_hour or 0)


# ---------------------------------------------------------------------------
# Item catalog + owner inventory
# ---------------------------------------------------------------------------


async def list_all_items() -> list[Item]:
    """Return every item defined in the static item catalog."""
    async with session_scope() as session:
        result = await session.execute(select(Item).order_by(Item.name))
        return list(result.scalars().all())


async def list_items_by_category(category: str) -> list[Item]:
    async with session_scope() as session:
        result = await session.execute(select(Item).where(Item.category == category).order_by(Item.name))
        return list(result.scalars().all())


async def get_item_by_name(name: str) -> Optional[Item]:
    async with session_scope() as session:
        return (await session.execute(select(Item).where(Item.name == name))).scalar_one_or_none()


async def get_owner_items(owner_discord_id: int) -> dict[str, int]:
    """Return a ``{item_name: count}`` mapping of everything the owner owns."""
    async with session_scope() as session:
        result = await session.execute(select(OwnerItem).where(OwnerItem.owner_discord_id == owner_discord_id))
        return {row.item_name: row.count for row in result.scalars().all() if row.count > 0}


async def get_owner_item_count(owner_discord_id: int, item_name: str) -> int:
    async with session_scope() as session:
        row = (
            await session.execute(
                select(OwnerItem).where(
                    OwnerItem.owner_discord_id == owner_discord_id,
                    OwnerItem.item_name == item_name,
                )
            )
        ).scalar_one_or_none()
        return int(row.count) if row is not None else 0


async def give_owner_item(owner_discord_id: int, item_name: str, amount: int) -> int:
    """Add ``amount`` of ``item_name`` to an owner's inventory. Returns new count."""
    async with session_scope() as session:
        row = (
            await session.execute(
                select(OwnerItem).where(
                    OwnerItem.owner_discord_id == owner_discord_id,
                    OwnerItem.item_name == item_name,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = OwnerItem(
                owner_discord_id=owner_discord_id,
                item_name=item_name,
                count=max(0, int(amount)),
            )
            session.add(row)
        else:
            row.count = max(0, int(row.count) + int(amount))
        await session.flush()
        return int(row.count)


async def consume_owner_item(owner_discord_id: int, item_name: str, amount: int = 1) -> bool:
    """
    Try to remove ``amount`` of ``item_name`` from the owner's inventory.
    Returns True on success, False if the owner didn't have enough.
    """
    if amount <= 0:
        return True
    async with session_scope() as session:
        row = (
            await session.execute(
                select(OwnerItem).where(
                    OwnerItem.owner_discord_id == owner_discord_id,
                    OwnerItem.item_name == item_name,
                )
            )
        ).scalar_one_or_none()
        if row is None or int(row.count) < int(amount):
            return False
        row.count = int(row.count) - int(amount)
        await session.flush()
        return True
