from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Text as SAText
from sqlalchemy import and_, case, cast, func, or_, select, true
from sqlalchemy.orm import selectinload

from .get import get_pooch_parents
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
    GraveyardPooch,
    HealthImpactWeight,
    HellPooch,
    Injury,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    OwnerServer,
    Pooch,
    PoochBreed,
    PoochDisease,
    PoochDiseaseImmunity,
    PoochInjury,
    PoochMutation,
    PoochParentage,
    PoochPregnancy,
    PoochSnapshot,
    Server,
    ServerEvent,
    ServerEventMenu,
    ServerEventMenuOption,
    ServerEventOccurrence,
    ServerEventOutcome,
    ServerEventParticipation,
    StrayEvent,
    StrayPooch,
    Vendor,
    VendorDesiredBreed,
    VendorDesiredMutation,
    VendorPoochForSale,
)
from .session import session_scope
from .utils import (
    check_owner_event_filter,
    get_matching_dead_pooch_ids_for_server,
    get_matching_hell_pooch_ids_for_server,
    get_matching_kennel_ids_for_owner,
    get_matching_pooch_ids_for_owner,
    get_matching_stray_pooch_ids_for_server_filtered,
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


async def list_all_injuries() -> list[Injury]:
    """
    Fetch every injury in alphabetical order by name.

    Returns
    -------
    list[Injury]
        Every ORM Injury object in the static injury table.
    """

    async with session_scope() as session:
        response = await session.execute(select(Injury).order_by(Injury.name.asc()))

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


async def list_owner_discord_ids_for_server(server_discord_id: int) -> list[int]:
    """Return the discord IDs of all owners that are members of the given server."""
    async with session_scope() as session:
        result = await session.execute(
            select(OwnerServer.owner_discord_id).where(OwnerServer.server_discord_id == server_discord_id)
        )
        return [row[0] for row in result.all()]


async def list_graveyard_pooches_for_owners(owner_ids: list[int]) -> list[Pooch]:
    """Return all graveyard pooches buried by any of the given owners."""
    async with session_scope() as session:
        if not owner_ids:
            return []
        result = await session.execute(
            select(Pooch)
            .join(GraveyardPooch, GraveyardPooch.pooch_id == Pooch.id)
            .where(GraveyardPooch.owner_discord_id.in_(owner_ids))
        )
        return list(result.scalars().all())


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


async def list_pooch_injuries(pooch_id: int) -> list[Injury]:
    """Fetch the list of injuries the given pooch has."""
    async with session_scope() as session:
        query = (
            select(Injury)
            .join(PoochInjury, PoochInjury.injury_id == Injury.id)
            .where(PoochInjury.pooch_id == pooch_id)
            .order_by(Injury.health_impact)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_pooch_injury_instances(pooch_id: int) -> list[PoochInjury]:
    """Fetch the PoochInjury join records for the given pooch, with the injury relationship eagerly loaded."""
    from sqlalchemy.orm import selectinload

    async with session_scope() as session:
        query = (
            select(PoochInjury)
            .options(selectinload(PoochInjury.injury))
            .where(PoochInjury.pooch_id == pooch_id)
            .order_by(PoochInjury.id)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_pooch_mutation_instances(pooch_id: int) -> list[PoochMutation]:
    """Fetch the PoochMutation join records for the given pooch, with the mutation relationship eagerly loaded."""
    from sqlalchemy.orm import selectinload

    async with session_scope() as session:
        query = (
            select(PoochMutation)
            .options(selectinload(PoochMutation.mutation))
            .where(PoochMutation.pooch_id == pooch_id)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_invisible_pooch_injury_instances(pooch_id: int) -> list[PoochInjury]:
    """Return all invisible PoochInjury records for the given pooch, with the injury eagerly loaded."""
    async with session_scope() as session:
        result = await session.execute(
            select(PoochInjury)
            .options(selectinload(PoochInjury.injury))
            .where(PoochInjury.pooch_id == pooch_id, PoochInjury.visible.is_(False))
        )
        return list(result.scalars().all())


async def list_invisible_pooch_mutation_instances(pooch_id: int) -> list[PoochMutation]:
    """Return all invisible PoochMutation records for the given pooch, with the mutation eagerly loaded."""
    async with session_scope() as session:
        result = await session.execute(
            select(PoochMutation)
            .options(selectinload(PoochMutation.mutation))
            .where(PoochMutation.pooch_id == pooch_id, PoochMutation.visible.is_(False))
        )
        return list(result.scalars().all())


async def list_invisible_pooch_disease_instances(pooch_id: int) -> list[PoochDisease]:
    """Return all invisible PoochDisease records for the given pooch, with the disease eagerly loaded."""
    async with session_scope() as session:
        result = await session.execute(
            select(PoochDisease)
            .options(selectinload(PoochDisease.disease))
            .where(PoochDisease.pooch_id == pooch_id, PoochDisease.visible.is_(False))
        )
        return list(result.scalars().all())


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


async def list_pooches_with_health(pooch_ids: set[int]) -> dict[int, dict]:
    """
    Batch-fetch pooch data with computed health in a single joined query.

    Parameters
    ----------
    pooch_ids: set[int]
        The set of pooch IDs to fetch.

    Returns
    -------
    dict[int, dict]
        A dict of {pooch_id: {id, name, sex, alive, age, health}}.
    """
    if not pooch_ids:
        return {}

    async with session_scope() as session:
        query = (
            select(
                Pooch.id,
                Pooch.name,
                Pooch.sex,
                Pooch.alive,
                Pooch.age,
                (
                    Pooch.base_health - Pooch.health_loss_age + func.coalesce(func.sum(HealthImpactWeight.weight), 0)
                ).label("health"),
            )
            .outerjoin(PoochMutation, PoochMutation.pooch_id == Pooch.id)
            .outerjoin(Mutation, Mutation.id == PoochMutation.mutation_id)
            .outerjoin(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(Pooch.id.in_(pooch_ids))
            .group_by(Pooch.id, Pooch.name, Pooch.sex, Pooch.alive, Pooch.age, Pooch.base_health, Pooch.health_loss_age)
        )
        rows = (await session.execute(query)).all()

    return {
        row[0]: {"id": row[0], "name": row[1], "sex": row[2], "alive": row[3], "age": row[4], "health": int(row[5])}
        for row in rows
    }


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


async def list_strays_for_server(server_discord_id: int) -> list[Pooch]:
    """
    List all alive stray pooches on a server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to list strays for.

    Returns
    -------
    list[Pooch]
        A list of alive Pooch ORM objects that are currently strays on the given server.
    """

    async with session_scope() as session:
        query = (
            select(Pooch)
            .join(StrayPooch, StrayPooch.pooch_id == Pooch.id)
            .where(StrayPooch.server_discord_id == server_discord_id, Pooch.alive.is_(True))
            .order_by(Pooch.id)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


async def count_owners_for_server(server_discord_id: int) -> int:
    """Return the number of owners registered on the given server."""
    async with session_scope() as session:
        result = await session.scalar(
            select(func.count(OwnerServer.owner_discord_id)).where(OwnerServer.server_discord_id == server_discord_id)
        )
        return result or 0


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


async def list_vendor_desired_mutations(vendor_id: int) -> list[Mutation]:
    """
    Fetch the mutations that the given vendor desires.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor.

    Returns
    -------
    list[Mutation]
        The list of Mutation ORM objects the vendor desires.
    """

    async with session_scope() as session:
        query = (
            select(Mutation)
            .join(VendorDesiredMutation, VendorDesiredMutation.mutation_id == Mutation.id)
            .where(VendorDesiredMutation.vendor_id == vendor_id)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_vendor_desired_breeds(vendor_id: int) -> list[Breed]:
    """
    Fetch the breeds that the given vendor desires (one per rarity tier).

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor.

    Returns
    -------
    list[Breed]
        The list of Breed ORM objects the vendor desires.
    """

    _RARITY_ORDER = ["common", "uncommon", "novel", "rare", "unprecedented", "remarkable", "extraordinary", "unique"]
    rarity_sort = case(
        {rarity: i for i, rarity in enumerate(_RARITY_ORDER)},
        value=cast(Breed.rarity, SAText),
        else_=len(_RARITY_ORDER),
    )

    async with session_scope() as session:
        query = (
            select(Breed)
            .join(VendorDesiredBreed, VendorDesiredBreed.breed_id == Breed.id)
            .where(VendorDesiredBreed.vendor_id == vendor_id)
            .order_by(rarity_sort)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_active_server_event_occurrences(server_discord_id: Optional[int] = None) -> list[ServerEventOccurrence]:
    """
    List active (unresolved, unarchived) server event occurrences, newest first.

    A server can have several at once (one per tier: a daily minor event and a weekly major one).

    Parameters
    ----------
    server_discord_id: Optional[int]
        Only this server's occurrences; every server's when None.
    """

    filters = [ServerEventOccurrence.archived.is_(False), ServerEventOccurrence.resolved_at.is_(None)]
    if server_discord_id is not None:
        filters.append(ServerEventOccurrence.server_discord_id == server_discord_id)

    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .where(*filters)
            .options(
                selectinload(ServerEventOccurrence.server_event).selectinload(ServerEvent.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.menus)
                .selectinload(ServerEventMenu.options)
                .selectinload(ServerEventMenuOption.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.outcomes)
                .selectinload(ServerEventOutcome.actions),
                selectinload(ServerEventOccurrence.participations),
            )
            .order_by(ServerEventOccurrence.triggered_at.desc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_server_event_participations(occurrence_id: int) -> list[ServerEventParticipation]:
    """
    List server event participations.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    Returns
    -------
    Any
        The result of calling `list_server_event_participations`.
    """

    async with session_scope() as session:
        query = (
            select(ServerEventParticipation)
            .where(ServerEventParticipation.occurrence_id == occurrence_id)
            .order_by(ServerEventParticipation.participated_at.asc())
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_server_event_history(server_discord_id: int, limit: int = 20) -> list[ServerEventOccurrence]:
    """
    List server event history.

    Parameters
    ----------
    server_discord_id: Any
        The `server_discord_id` value.

    limit: Any
        The `limit` value.

    Returns
    -------
    Any
        The result of calling `list_server_event_history`.
    """

    async with session_scope() as session:
        query = (
            select(ServerEventOccurrence)
            .where(
                ServerEventOccurrence.server_discord_id == server_discord_id, ServerEventOccurrence.archived.is_(True)
            )
            .options(
                selectinload(ServerEventOccurrence.server_event).selectinload(ServerEvent.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.menus)
                .selectinload(ServerEventMenu.options)
                .selectinload(ServerEventMenuOption.actions),
                selectinload(ServerEventOccurrence.server_event)
                .selectinload(ServerEvent.outcomes)
                .selectinload(ServerEventOutcome.actions),
                selectinload(ServerEventOccurrence.participations),
            )
            .order_by(ServerEventOccurrence.triggered_at.desc())
            .limit(limit)
        )
        response = await session.execute(query)

    return list(response.scalars().all())


async def list_matching_pooch_ids(owner_discord_id: int, filter_spec: dict | None) -> list[int]:
    """
    List matching pooch ids.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    filter_spec: Any
        The `filter_spec` value.

    Returns
    -------
    Any
        The result of calling `list_matching_pooch_ids`.
    """

    async with session_scope() as session:
        return await get_matching_pooch_ids_for_owner(session, owner_discord_id, filter_spec or {})


async def list_matching_pooch_ids_in_kennel(
    owner_discord_id: int, kennel_id: int, filter_spec: dict | None
) -> list[int]:
    """
    List matching pooch ids in kennel.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    kennel_id: Any
        The `kennel_id` value.

    filter_spec: Any
        The `filter_spec` value.

    Returns
    -------
    Any
        The result of calling `list_matching_pooch_ids_in_kennel`.
    """

    async with session_scope() as session:
        return await get_matching_pooch_ids_for_owner(session, owner_discord_id, filter_spec or {}, kennel_id=kennel_id)


async def list_matching_kennel_ids(owner_discord_id: int, filter_spec: dict | None) -> list[int]:
    """
    List matching kennel ids.

    Parameters
    ----------
    owner_discord_id: Any
        The `owner_discord_id` value.

    filter_spec: Any
        The `filter_spec` value.

    Returns
    -------
    Any
        The result of calling `list_matching_kennel_ids`.
    """

    async with session_scope() as session:
        return await get_matching_kennel_ids_for_owner(session, owner_discord_id, filter_spec or {})


async def list_all_stray_events() -> list[StrayEvent]:
    """
    List all stray events.

    Returns
    -------
    Any
        The result of calling `list_all_stray_events`.
    """

    from sqlalchemy.orm import selectinload

    async with session_scope() as session:
        query = (
            select(StrayEvent).options(selectinload(StrayEvent.actions)).order_by(StrayEvent.category, StrayEvent.name)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_matching_stray_pooch_ids(server_discord_id: int, filter_spec: dict | None) -> list[int]:
    """Return IDs of alive strays on the server that match the given pooch filter."""
    from .utils import get_matching_stray_pooch_ids_for_server

    async with session_scope() as session:
        return await get_matching_stray_pooch_ids_for_server(session, server_discord_id, filter_spec or {})


async def list_matching_stray_pooch_ids_filtered(server_discord_id: int, filter_spec: dict | None) -> list[int]:
    """Like list_matching_stray_pooch_ids but strips count metadata fields from the filter first."""
    async with session_scope() as session:
        return await get_matching_stray_pooch_ids_for_server_filtered(session, server_discord_id, filter_spec)


async def list_matching_dead_pooch_ids_for_server(server_discord_id: int, filter_spec: dict | None) -> list[int]:
    """Return IDs of dead pooches (graveyard) owned by server members that match the given filter."""
    async with session_scope() as session:
        return await get_matching_dead_pooch_ids_for_server(session, server_discord_id, filter_spec)


async def list_matching_hell_pooch_ids_for_server(server_discord_id: int, filter_spec: dict | None) -> list[int]:
    """Return IDs of hell pooches owned by server members that match the given filter."""
    async with session_scope() as session:
        return await get_matching_hell_pooch_ids_for_server(session, server_discord_id, filter_spec)


async def list_active_sale_listings_for_server(server_discord_id: int) -> list[AuctionSaleListing]:
    """All active sale listings on a server, ordered by created_at DESC."""
    async with session_scope() as session:
        query = (
            select(AuctionSaleListing)
            .where(
                AuctionSaleListing.server_discord_id == server_discord_id,
                AuctionSaleListing.is_active.is_(True),
            )
            .order_by(AuctionSaleListing.created_at.desc())
        )
        return list((await session.execute(query)).scalars().all())


async def list_active_sale_listings_for_owner(owner_discord_id: int) -> list[AuctionSaleListing]:
    """All active listings where the owner is the seller."""
    async with session_scope() as session:
        query = (
            select(AuctionSaleListing)
            .where(
                AuctionSaleListing.seller_discord_id == owner_discord_id,
                AuctionSaleListing.is_active.is_(True),
            )
            .order_by(AuctionSaleListing.created_at.desc())
        )
        return list((await session.execute(query)).scalars().all())


async def list_active_bounty_listings_for_server(server_discord_id: int) -> list[AuctionBountyListing]:
    """All active bounty listings on a server, ordered by created_at DESC."""
    async with session_scope() as session:
        query = (
            select(AuctionBountyListing)
            .where(
                AuctionBountyListing.server_discord_id == server_discord_id,
                AuctionBountyListing.is_active.is_(True),
            )
            .order_by(AuctionBountyListing.created_at.desc())
        )
        return list((await session.execute(query)).scalars().all())


async def list_active_bounty_listings_for_owner(owner_discord_id: int) -> list[AuctionBountyListing]:
    """All active bounty listings created by this owner."""
    async with session_scope() as session:
        query = (
            select(AuctionBountyListing)
            .where(
                AuctionBountyListing.buyer_discord_id == owner_discord_id,
                AuctionBountyListing.is_active.is_(True),
            )
            .order_by(AuctionBountyListing.created_at.desc())
        )
        return list((await session.execute(query)).scalars().all())


async def list_bids_for_listing(listing_id: int) -> list[AuctionBid]:
    """All bids for a listing, ordered by amount DESC."""
    async with session_scope() as session:
        query = select(AuctionBid).where(AuctionBid.listing_id == listing_id).order_by(AuctionBid.amount.desc())
        return list((await session.execute(query)).scalars().all())


async def list_expired_sale_listings() -> list[AuctionSaleListing]:
    """Active listings whose expiry time has passed."""
    async with session_scope() as session:
        now = datetime.now(timezone.utc)
        query = select(AuctionSaleListing).where(
            AuctionSaleListing.is_active.is_(True),
            AuctionSaleListing.expires_at.is_not(None),
            AuctionSaleListing.expires_at <= now,
        )
        return list((await session.execute(query)).scalars().all())


async def list_owner_bid_history(owner_discord_id: int) -> list[AuctionBid]:
    """All bids ever placed by this owner, newest first."""
    async with session_scope() as session:
        query = (
            select(AuctionBid)
            .where(AuctionBid.bidder_discord_id == owner_discord_id)
            .order_by(AuctionBid.placed_at.desc())
        )
        return list((await session.execute(query)).scalars().all())


async def list_pooch_snapshots(pooch_id: int) -> list[PoochSnapshot]:
    """Return all timeline snapshots for a pooch, oldest first."""
    async with session_scope() as session:
        query = (
            select(PoochSnapshot)
            .where(PoochSnapshot.pooch_id == pooch_id)
            .order_by(PoochSnapshot.snapshot_at.asc(), PoochSnapshot.id.asc())
        )
        return list((await session.execute(query)).scalars().all())


async def list_all_diseases(season: str | None = None) -> list[Disease]:
    """Fetch every disease in alphabetical order by name, optionally filtering by season."""
    async with session_scope() as session:
        query = select(Disease)
        if season is not None:
            query = query.where(or_(Disease.seasons.is_(None), Disease.seasons.any(season)))
        response = await session.execute(query.order_by(Disease.name.asc()))
    return list(response.scalars().all())


async def list_pooch_diseases(pooch_id: int) -> list[Disease]:
    """Fetch the list of diseases the given pooch currently has."""
    async with session_scope() as session:
        query = (
            select(Disease)
            .join(PoochDisease, PoochDisease.disease_id == Disease.id)
            .where(PoochDisease.pooch_id == pooch_id)
            .order_by(Disease.name)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_pooch_disease_instances(pooch_id: int) -> list[PoochDisease]:
    """Fetch the PoochDisease join records for the given pooch, with the disease relationship eagerly loaded."""
    from sqlalchemy.orm import selectinload

    async with session_scope() as session:
        query = (
            select(PoochDisease)
            .options(selectinload(PoochDisease.disease))
            .where(PoochDisease.pooch_id == pooch_id)
            .order_by(PoochDisease.id)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_pooch_disease_immunities(pooch_id: int) -> list[PoochDiseaseImmunity]:
    """Fetch all PoochDiseaseImmunity records for the given pooch, with the disease relationship eagerly loaded."""
    from sqlalchemy.orm import selectinload

    async with session_scope() as session:
        query = (
            select(PoochDiseaseImmunity)
            .options(selectinload(PoochDiseaseImmunity.disease))
            .where(PoochDiseaseImmunity.pooch_id == pooch_id)
            .order_by(PoochDiseaseImmunity.id)
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_pooches_with_disease_in_kennel(kennel_id: int, disease_id: int) -> list[int]:
    """Return IDs of living pooches in the given kennel that currently have the given disease."""
    async with session_scope() as session:
        query = (
            select(Pooch.id)
            .join(KennelPooch, KennelPooch.pooch_id == Pooch.id)
            .join(PoochDisease, PoochDisease.pooch_id == Pooch.id)
            .where(
                KennelPooch.kennel_id == kennel_id,
                PoochDisease.disease_id == disease_id,
                Pooch.alive.is_(True),
            )
        )
        response = await session.execute(query)
    return list(response.scalars().all())


async def list_pooch_ids_on_breeding_cooldown() -> list[int]:
    """Return the IDs of living pooches whose breeding cooldown is above 0, leaving out pregnant ones."""
    async with session_scope() as session:
        result = await session.execute(
            select(Pooch.id).where(Pooch.alive.is_(True), Pooch.breeding_cooldown > 0, Pooch.pregnancy_timer.is_(None))
        )
        return list(result.scalars().all())


async def list_persistent_injury_instances() -> list[tuple[int, int]]:
    """Return ``(pooch_injury_id, pooch_id)`` for every injury with a persistence counter on a living pooch."""
    async with session_scope() as session:
        result = await session.execute(
            select(PoochInjury.id, PoochInjury.pooch_id)
            .join(Pooch, Pooch.id == PoochInjury.pooch_id)
            .where(Pooch.alive.is_(True), PoochInjury.persistence.is_not(None))
        )
        return [(row[0], row[1]) for row in result.all()]
