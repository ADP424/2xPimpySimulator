from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.orm import selectinload

from .get import get_pooch_parents
from .models import (
    Breed,
    Event,
    EventOccurrence,
    EventOption,
    EventOutcome,
    GraveyardPooch,
    HealthImpactWeight,
    HellPooch,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    OwnerServer,
    Pooch,
    PoochBreed,
    PoochMutation,
    PoochParentage,
    PoochPregnancy,
    Server,
    ServerEvent,
    ServerEventOccurrence,
    ServerEventOption,
    ServerEventOutcome,
    ServerEventParticipation,
    Vendor,
    VendorPoochForSale,
)
from .session import session_scope
from .utils import (
    check_owner_event_filter,
    get_matching_kennel_ids_for_owner,
    get_matching_pooch_ids_for_owner,
)


async def list_active_owner_events_for_owner(
    owner_discord_id: int, pending_only: bool = False
) -> list[EventOccurrence]:
    """
    List all active events for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    pending_only: bool
        If True, only return events that haven't been responded to.

    Returns
    -------
    list[EventOccurrence]
        A list of EventOccurrence ORM objects for the owner.
    """

    async with session_scope() as session:
        conditions = [EventOccurrence.owner_discord_id == owner_discord_id, EventOccurrence.archived.is_(False)]
        if pending_only:
            conditions.append(EventOccurrence.responded_at.is_(None))

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
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_all_breeds() -> list[Breed]:
    """
    Fetch every breed in alphabetical order by category, then by name.

    Returns
    -------
    list[Breed]
        Every ORM Breed object in the static breed table.
    """

    async with session_scope() as session:
        response = await session.execute(select(Breed).order_by(Breed.category.asc(), Breed.name.asc(), Breed.id.asc()))

    return list(response.scalars().all())


async def list_all_owner_events() -> list[Event]:
    """
    List all owner_events.

    Returns
    -------
    list[Event]
        A list of all Event ORM objects.
    """

    async with session_scope() as session:
        query = (
            select(Event)
            .options(
                selectinload(Event.actions),
                selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(Event.options).selectinload(EventOption.outcomes).selectinload(EventOutcome.actions),
            )
            .order_by(Event.category, Event.name)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_all_mutations() -> list[Mutation]:
    """
    Fetch every mutation in alphabetical order by category, then by name.

    Returns
    -------
    list[Mutation]
        Every ORM Mutation object in the static mutation table.
    """

    async with session_scope() as session:
        response = await session.execute(
            select(Mutation).order_by(Mutation.category.asc(), Mutation.name.asc(), Mutation.id.asc())
        )

    return list(response.scalars().all())


async def list_eligible_owner_events_for_owner(
    owner_discord_id: int, include_triggered_only: bool = False
) -> list[Event]:
    """
    List all events that an owner is eligible for based on their current state.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    include_triggered_only: bool, default : False
        Whether to include events that are supposed to only be triggered by other events or not.

    Returns
    -------
    list[Event]
        A list of Event ORM objects the owner is eligible for.
    """

    async with session_scope() as session:
        owner_query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner_result = await session.execute(owner_query)
        owner = owner_result.scalar_one_or_none()

        if owner is None:
            return []

        query = (
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
        response = await session.execute(query)
        events = list(response.scalars().all())

        eligible_events: list[Event] = []
        for event in events:
            if await check_owner_event_filter(session, owner_discord_id, event.filter):
                eligible_events.append(event)

    return eligible_events


async def list_owner_event_history_for_owner(owner_discord_id: int, limit: int = 50) -> list[EventOccurrence]:
    """
    List event history for an owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    limit: int
        Maximum number of records to return.

    Returns
    -------
    list[EventOccurrence]
        A list of EventOccurrence ORM objects for the owner.
    """

    async with session_scope() as session:
        query = (
            select(EventOccurrence)
            .where(EventOccurrence.owner_discord_id == owner_discord_id, EventOccurrence.archived.is_(True))
            .options(
                selectinload(EventOccurrence.event).selectinload(Event.actions),
                selectinload(EventOccurrence.event).selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(EventOccurrence.event)
                .selectinload(Event.options)
                .selectinload(EventOption.outcomes)
                .selectinload(EventOutcome.actions),
                selectinload(EventOccurrence.selected_option).selectinload(EventOption.actions),
                selectinload(EventOccurrence.selected_option)
                .selectinload(EventOption.outcomes)
                .selectinload(EventOutcome.actions),
            )
            .order_by(EventOccurrence.completed_at.desc(), EventOccurrence.triggered_at.desc())
            .limit(limit)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_owner_events_by_category(category: str) -> list[Event]:
    """
    List all events in a specific category.

    Parameters
    ----------
    category: str
        The category to filter by.

    Returns
    -------
    list[Event]
        A list of Event ORM objects in the specified category.
    """

    async with session_scope() as session:
        query = (
            select(Event)
            .where(Event.category == category)
            .options(
                selectinload(Event.actions),
                selectinload(Event.options).selectinload(EventOption.actions),
                selectinload(Event.options).selectinload(EventOption.outcomes).selectinload(EventOutcome.actions),
            )
            .order_by(Event.name)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_expired_active_owner_events() -> list[EventOccurrence]:
    """
    List all active events that have expired without a response.

    Returns
    -------
    list[EventOccurrence]
        A list of expired EventOccurrence ORM objects.
    """

    async with session_scope() as session:
        now = datetime.now(timezone.utc)
        query = (
            select(EventOccurrence)
            .where(
                and_(
                    EventOccurrence.archived.is_(False),
                    EventOccurrence.responded_at.is_(None),
                    EventOccurrence.expires_at.isnot(None),
                    EventOccurrence.expires_at < now,
                )
            )
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

    return list(response.scalars().all())


async def list_graveyard_pooches_for_owner(owner_discord_id: int) -> list[tuple[Pooch, datetime]]:
    """
    Fetch the list of deceased pooches buried by the owner with the given Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch the buried pooches for.

    Returns
    -------
    list[tuple[Pooch, datetime]]
        A list of (Pooch ORM object, buried_at datetime) tuples, most recently buried first.
    """

    async with session_scope() as session:
        query = (
            select(Pooch, GraveyardPooch.buried_at)
            .join(GraveyardPooch, GraveyardPooch.pooch_id == Pooch.id)
            .where(GraveyardPooch.owner_discord_id == owner_discord_id)
            .order_by(GraveyardPooch.buried_at.desc(), Pooch.id.desc())
        )
        response = await session.execute(query)

    return [(pooch, buried_at) for pooch, buried_at in response.tuples().all()]


async def list_hell_pooches() -> list[Pooch]:
    """
    Fetch the list of pooches sacrificed to Hell. This is global between servers.

    Returns
    -------
    list[Pooch]
        A list of Pooch ORM objects representing all the pooches in Hell, most recently damned first.
    """

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(HellPooch, HellPooch.pooch_id == Pooch.id)
            .order_by(HellPooch.damned_at.desc(), Pooch.id.desc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_kennels_for_owner(owner_discord_id: int) -> list[Kennel]:
    """
    Fetch the list of kennels owned by the owner with the given Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch the kennels for.

    Returns
    -------
    list[Kennel]
        The list of Kennel ORM objects the owner owns.
    """

    async with session_scope() as session:
        owner = (await session.execute(select(Owner).where(Owner.discord_id == owner_discord_id))).scalar_one_or_none()
        if owner is None:
            return []

        query = (
            select(Kennel)
            .where(Kennel.owner_discord_id == owner.discord_id)
            .order_by(Kennel.created_at.asc(), Kennel.id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_living_pooches() -> list[Pooch]:
    """
    Fetch a list of every living pooch.

    Returns
    -------
    list[Pooch]
        The list of every living pooch across all servers.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.alive == True).order_by(Pooch.created_at.asc(), Pooch.id.asc())  # noqa: E712
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_owner_servers(owner_discord_id: int) -> list[Server]:
    """
    Fetch a list of all the servers the owner with the given Discord ID is in.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to get the servers for.

    Returns
    -------
    list[Server]
        The list of Server ORM objects the given owner belongs to.
    """

    async with session_scope() as session:
        query = (
            select(Server)
            .join(OwnerServer, OwnerServer.server_discord_id == Server.discord_id)
            .where(OwnerServer.owner_discord_id == owner_discord_id)
            .order_by(Server.joined_at.asc(), Server.discord_id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_owners() -> list[Owner]:
    """
    List all owners in the database.

    Returns
    -------
    list[Owner]
        A list of every Owner ORM object.
    """

    async with session_scope() as session:
        query = select(Owner)
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_pooch_breed_weights(pooch_id: int) -> list[tuple[int, int]]:
    """
    Fetch the list of breed weights the given pooch has.
    Returns the integer weights stored in the `pooch_breeds` relationship table. Useful for
    deterministic calculations (like inheritance) where you want the underlying weights rather
    than the normalized relative weights returned by `list_pooch_breeds`.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the breeds of.

    Returns
    -------
    list[tuple[int, int]]
        A list of `(breed_id, weight)` pairs.
    """

    async with session_scope() as session:
        query = select(PoochBreed.breed_id, PoochBreed.weight).where(PoochBreed.pooch_id == pooch_id)
        response = await session.execute(query)

    return [(breed_id, weight) for breed_id, weight in response.tuples().all()]


async def list_pooch_breeds(pooch_id: int) -> list[tuple[Breed, float]]:
    """
    Fetch the list of breeds the given pooch has, plus the relative weight of that breed in the pooch.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the breeds of.

    Returns
    -------
    list[tuple[Breed, float]]
        The list of Breed ORM objects and their relative weight on the connected pooch in the form `(breed, weight)`.
    """

    async with session_scope() as session:
        total_weight_subquery = (
            select(func.sum(PoochBreed.weight)).where(PoochBreed.pooch_id == pooch_id).scalar_subquery()
        )
        query = (
            select(Breed, (PoochBreed.weight / total_weight_subquery).label("relative_weight"))
            .join(PoochBreed, PoochBreed.breed_id == Breed.id)
            .where(PoochBreed.pooch_id == pooch_id)
        )
        response = await session.execute(query)

    return [(breed, float(weight)) for breed, weight in list(response.tuples().all())]


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


async def list_pooch_mutations(
    pooch_id: int, positive: bool = True, negative: bool = True, neutral: bool = True
) -> list[Mutation]:
    """
    Fetch the list of mutations the given pooch has.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the mutations of.

    positive: bool, default : True
        Whether to include mutations with positive health impacts or not (> 0).

    negative: bool, default : True
        Whether to include mutations with negative health impacts or not (< 0).

    neutral: bool, default : True
        Whether to include mutations with neutral health impacts or not (= 0).

    Returns
    -------
    list[Mutation]
        The list of Mutation ORM objects connected to the pooch.
    """

    async with session_scope() as session:
        query = (
            select(Mutation)
            .join(PoochMutation, PoochMutation.mutation_id == Mutation.id)
            .join(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(PoochMutation.pooch_id == pooch_id)
        )

        conditions = []
        if positive:
            conditions.append(HealthImpactWeight.weight > 0)
        if negative:
            conditions.append(HealthImpactWeight.weight < 0)
        if neutral:
            conditions.append(HealthImpactWeight.weight == 0)

        if not conditions:
            return []

        query = query.where(or_(*conditions))
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_pooch_pregnancies() -> list[PoochPregnancy]:
    """
    Fetch a list of every all pooch pregnancy instances.

    Returns
    -------
    list[PoochPregnancy]
        The list of PoochPregnancy ORM relationship objects across all servers.
    """

    async with session_scope() as session:
        response = await session.execute(select(PoochPregnancy).order_by(PoochPregnancy.fetus_id.asc()))

    return list(response.scalars().all())


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


async def list_servers() -> list[Server]:
    """
    Fetch a list of all servers in the database.

    Returns
    -------
    list[Server]
        The list of all Server ORM objects in the database.
    """

    async with session_scope() as session:
        query = select(Server).order_by(Server.joined_at.asc(), Server.discord_id.asc())
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_servers_for_pooch(pooch_id: int) -> list[Server]:
    """
    Fetch a list of all the servers in which a pooch is relevant.
    A pooch is relevant in a server if their owner is in the server (player or vendor).

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the servers for.

    Returns
    -------
    list[Server]
        The list of Server ORM objects the given pooch vicariously belongs to.
    """

    async with session_scope() as session:
        query = (
            select(Server)
            .distinct()
            .outerjoin(Vendor, Vendor.server_discord_id == Server.discord_id)
            .outerjoin(OwnerServer, OwnerServer.server_discord_id == Server.discord_id)
            .join(Pooch, or_(Pooch.vendor_id == Vendor.id, Pooch.owner_discord_id == OwnerServer.owner_discord_id))
            .where(Pooch.id == pooch_id)
            .order_by(Server.joined_at.asc(), Server.discord_id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_servers_for_owner(owner_discord_id: int) -> list[Server]:
    """
    Fetch all servers the given owner belongs to.
    """

    async with session_scope() as session:
        query = (
            select(Server)
            .join(OwnerServer, OwnerServer.server_discord_id == Server.discord_id)
            .where(OwnerServer.owner_discord_id == owner_discord_id)
            .order_by(Server.joined_at.asc(), Server.discord_id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_vendor_pooch_stock(vendor_id: int) -> list[Pooch]:
    """
    Fetch a list of every pooch a given vendor has for sale.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to fetch the pooches from.

    Returns
    -------
    list[Pooch]
        The list of Pooch ORM objects representing the pooches the given vendor has for sale.
    """

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(VendorPoochForSale, VendorPoochForSale.pooch_id == Pooch.id)
            .where(VendorPoochForSale.vendor_id == vendor_id)
            .order_by(Pooch.created_at.asc(), Pooch.id.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_vendors(server_discord_id: int) -> list[Vendor]:
    """
    Fetch the list of vendors for a given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to fetch the vendors of.

    Returns
    -------
    list[Vendor]
        The list of Vendor ORM objects belonging to the given server.
    """

    async with session_scope() as session:
        response = await session.execute(
            select(Vendor)
            .where(Vendor.server_discord_id == server_discord_id)
            .order_by(Vendor.name.asc(), Vendor.id.asc())
        )

    return list(response.scalars().all())


async def list_active_server_event_occurrences() -> list[ServerEventOccurrence]:
    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .where(ServerEventOccurrence.archived.is_(False), ServerEventOccurrence.resolved_at.is_(None))
            .options(
                selectinload(ServerEventOccurrence.server_event).selectinload(ServerEvent.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.options)
                .selectinload(ServerEventOption.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.outcomes)
                .selectinload(ServerEventOutcome.actions),
                selectinload(ServerEventOccurrence.participations).selectinload(
                    ServerEventParticipation.selected_option
                ),
            )
            .order_by(ServerEventOccurrence.triggered_at.desc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_server_event_participations(occurrence_id: int) -> list[ServerEventParticipation]:
    async with session_scope() as session:
        query = (
            select(ServerEventParticipation)
            .where(ServerEventParticipation.occurrence_id == occurrence_id)
            .options(selectinload(ServerEventParticipation.selected_option))
            .order_by(ServerEventParticipation.participated_at.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_server_event_history(server_discord_id: int, limit: int = 20) -> list[ServerEventOccurrence]:
    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .where(
                ServerEventOccurrence.server_discord_id == server_discord_id, ServerEventOccurrence.archived.is_(True)
            )
            .options(
                selectinload(ServerEventOccurrence.server_event).selectinload(ServerEvent.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.options)
                .selectinload(ServerEventOption.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.outcomes)
                .selectinload(ServerEventOutcome.actions),
                selectinload(ServerEventOccurrence.participations).selectinload(
                    ServerEventParticipation.selected_option
                ),
            )
            .order_by(ServerEventOccurrence.triggered_at.desc())
            .limit(limit)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_matching_pooch_ids(owner_discord_id: int, filter_spec: dict | None) -> list[int]:
    async with session_scope() as session:
        return await get_matching_pooch_ids_for_owner(session, owner_discord_id, filter_spec or {})


async def list_matching_pooch_ids_in_kennel(
    owner_discord_id: int, kennel_id: int, filter_spec: dict | None
) -> list[int]:
    async with session_scope() as session:
        return await get_matching_pooch_ids_for_owner(session, owner_discord_id, filter_spec or {}, kennel_id=kennel_id)


async def list_matching_kennel_ids(owner_discord_id: int, filter_spec: dict | None) -> list[int]:
    async with session_scope() as session:
        return await get_matching_kennel_ids_for_owner(session, owner_discord_id, filter_spec or {})
