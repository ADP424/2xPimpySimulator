import random
from typing import Optional

from sqlalchemy import and_, func, not_, select, true
from sqlalchemy.orm import selectinload

from .models import (
    Breed,
    Event,
    EventOccurrence,
    EventOption,
    EventOutcome,
    HealthImpactWeight,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    OwnerServer,
    Pooch,
    PoochBreed,
    PoochMutation,
    PoochParentage,
    RarityWeight,
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
from .utils import check_owner_event_filter, weighted_choice


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


async def get_random_breed_ids(
    n: int,
    rng: Optional[random.Random] = None,
    from_vendor: bool = False,
    from_ritual: bool = False,
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
        query = select(Breed, RarityWeight.weight).join(RarityWeight, RarityWeight.rarity == Breed.rarity)
        if from_vendor:
            query = query.where(not_(Breed.parameters.contains({"sold_by_vendors": False})))
        if from_ritual:
            query = query.where(not_(Breed.parameters.contains({"born_from_ritual": False})))
        response = await session.execute(query)
        rows = [(breed, weight) for breed, weight in response.tuples().all()]

    if not rows:
        return result

    for _ in range(n):
        breed = weighted_choice(rng, rows)
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


async def get_pooch_health(pooch_id: int) -> Optional[int]:
    """
    Get the current health of the given pooch, taking into account age and mutations.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the health of.

    Returns
    -------
    int, optional
        The current health of the pooch, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = (
            select(Pooch.base_health - Pooch.health_loss_age + func.coalesce(func.sum(HealthImpactWeight.weight), 0))
            .outerjoin(PoochMutation, PoochMutation.pooch_id == Pooch.id)
            .outerjoin(Mutation, Mutation.id == PoochMutation.mutation_id)
            .outerjoin(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(Pooch.id == pooch_id)
            .group_by(Pooch.id, Pooch.base_health, Pooch.health_loss_age)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def _get_pooch_stat(pooch_id: int, stat: str) -> Optional[int]:
    """
    Return the effective value of a single stat for the given pooch, accounting for
    mutation and breed `{stat}_add` / `{stat}_mult` parameters.

    Add modifiers are summed first, then mult modifiers are applied. Mutation mults
    multiply together; breed mults are weighted-averaged by the breed's relative weight
    in the pooch. The final value is rounded to the nearest integer.
    """

    async with session_scope() as session:
        pooch = await session.scalar(select(Pooch).where(Pooch.id == pooch_id))
        if pooch is None:
            return None

        base: int = getattr(pooch, stat)

        mutations = (
            (
                await session.execute(
                    select(Mutation)
                    .join(PoochMutation, PoochMutation.mutation_id == Mutation.id)
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

    total = float(base)

    mut_add = sum(m.parameters.get(f"{stat}_add", 0) for m in mutations)
    mut_mult = 1.0
    for m in mutations:
        mut_mult *= m.parameters.get(f"{stat}_mult", 1.0)
    total = (total + mut_add) * mut_mult

    total_weight = sum(w for _, w in breed_rows)
    if total_weight > 0:
        breed_add = sum(b.parameters.get(f"{stat}_add", 0) * (w / total_weight) for b, w in breed_rows)
        breed_mult = sum(b.parameters.get(f"{stat}_mult", 1.0) * (w / total_weight) for b, w in breed_rows)
        total = (total + breed_add) * breed_mult

    return round(total)


async def get_pooch_base_health(pooch_id: int) -> Optional[int]:
    """Return the effective base health of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "base_health")


async def get_pooch_strength(pooch_id: int) -> Optional[int]:
    """Return the effective strength of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "strength")


async def get_pooch_cuteness(pooch_id: int) -> Optional[int]:
    """Return the effective cuteness of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "cuteness")


async def get_pooch_fluffiness(pooch_id: int) -> Optional[int]:
    """Return the effective fluffiness of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "fluffiness")


async def get_pooch_intelligence(pooch_id: int) -> Optional[int]:
    """Return the effective intelligence of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "intelligence")


async def get_pooch_dexterity(pooch_id: int) -> Optional[int]:
    """Return the effective dexterity of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "dexterity")


async def get_pooch_fertility(pooch_id: int) -> Optional[int]:
    """Return the effective fertility of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "fertility")


async def get_pooch_aggressiveness(pooch_id: int) -> Optional[int]:
    """Return the effective aggressiveness of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "aggressiveness")


async def get_pooch_constitution(pooch_id: int) -> Optional[int]:
    """Return the effective constitution of the pooch, accounting for mutation/breed stat parameters."""
    return await _get_pooch_stat(pooch_id, "constitution")


async def get_pooch_size(pooch_id: int) -> Optional[int]:
    """Return the stored size of the pooch (raw column value, not breed-derived)."""
    async with session_scope() as session:
        result = await session.scalar(select(Pooch.size).where(Pooch.id == pooch_id))
    return result


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
            select(Event, RarityWeight.weight)
            .join(RarityWeight, RarityWeight.rarity == Event.rarity)
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
        rows = [(event, weight) for event, weight in event_response.tuples().all()]

        if not rows:
            return None

        eligible_rows: list[tuple[Event, float]] = []
        for event, weight in rows:
            if await check_owner_event_filter(session, owner_discord_id, event.filter):
                eligible_rows.append((event, weight))

        if not eligible_rows:
            return None

        return weighted_choice(rng, eligible_rows)


async def check_owner_event_filter_for_owner(owner_discord_id: int, filter_spec: dict | None) -> bool:
    async with session_scope() as session:
        return await check_owner_event_filter(session, owner_discord_id, filter_spec or {})


async def get_random_matching_pooch_id(
    owner_discord_id: int,
    filter_spec: dict | None,
    rng: random.Random,
) -> Optional[int]:
    from .utils import get_random_matching_pooch_id_for_owner

    async with session_scope() as session:
        return await get_random_matching_pooch_id_for_owner(session, owner_discord_id, filter_spec or {}, rng)


async def get_random_matching_kennel_id(
    owner_discord_id: int,
    filter_spec: dict | None,
    rng: random.Random,
) -> Optional[int]:
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
    async with session_scope() as session:
        query = select(ServerEvent).where(ServerEvent.id == server_event_id).options(*_server_event_load_options())
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_server_event_menu_option_by_id(option_id: int) -> Optional[ServerEventMenuOption]:
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


async def get_server_event_participation(
    occurrence_id: int, owner_discord_id: int
) -> Optional[ServerEventParticipation]:
    async with session_scope() as session:
        query = select(ServerEventParticipation).where(
            ServerEventParticipation.occurrence_id == occurrence_id,
            ServerEventParticipation.owner_discord_id == owner_discord_id,
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def list_all_server_events_with_weights() -> list[tuple[ServerEvent, int]]:
    """Return all server events paired with their rarity weight, fully loaded."""
    async with session_scope() as session:
        event_query = (
            select(ServerEvent, RarityWeight.weight)
            .join(RarityWeight, RarityWeight.rarity == ServerEvent.rarity)
            .options(*_server_event_load_options())
        )
        response = await session.execute(event_query)
        return [(event, weight) for event, weight in response.tuples().all()]


def _stray_event_load_options():
    return [
        selectinload(StrayEvent.actions),
        selectinload(StrayEvent.outcomes).selectinload(StrayEventOutcome.actions),
    ]


async def get_stray_event_by_id(stray_event_id: int) -> Optional[StrayEvent]:
    async with session_scope() as session:
        query = select(StrayEvent).where(StrayEvent.id == stray_event_id).options(*_stray_event_load_options())
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_stray_event_by_name(name: str) -> Optional[StrayEvent]:
    async with session_scope() as session:
        query = select(StrayEvent).where(StrayEvent.name == name).options(*_stray_event_load_options())
        response = await session.execute(query)
    return response.scalar_one_or_none()


async def get_random_eligible_stray_event_for_server(
    server_discord_id: int,
    rng: Optional[random.Random] = None,
    include_triggered_only: bool = False,
) -> Optional[StrayEvent]:
    """
    Pick a random stray event weighted by rarity, from those whose top-level filter is satisfied
    by the current stray population of the given server.
    """
    from .utils import check_stray_event_filter

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:
        query = (
            select(StrayEvent, RarityWeight.weight)
            .join(RarityWeight, RarityWeight.rarity == StrayEvent.rarity)
            .where(
                true() if include_triggered_only else StrayEvent.triggered_only.is_(False),
            )
            .options(*_stray_event_load_options())
        )
        response = await session.execute(query)
        rows = [(event, weight) for event, weight in response.tuples().all()]

        if not rows:
            return None

        eligible_rows: list[tuple[StrayEvent, float]] = []
        for event, weight in rows:
            if await check_stray_event_filter(session, server_discord_id, event.filter):
                eligible_rows.append((event, weight))

        if not eligible_rows:
            return None

        return weighted_choice(rng, eligible_rows)
