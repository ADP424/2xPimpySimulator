import random
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, bindparam, delete, func, not_, or_, select, update
from sqlalchemy.orm import selectinload

from .constants import (
    KENNEL_POOCH_LIMIT,
    POOCH_BASE_HEALTH,
    POOCH_BREEDING_COOLDOWN,
    POOCH_FETAL_AGE,
    POOCH_HEALTH_LOSS_AGE,
    POOCH_STAT_DEFAULT,
    RANDOM_SEED_SIZE_LIMIT,
    VENDOR_DESIRED_MUTATION_COUNT_RANGE,
    VENDOR_PRICE_MARKUP,
)
from .get import get_owner_by_discord_id, get_pooch_by_id, get_vendor_by_id
from .models import (
    SNAPSHOT_BIRTH,
    SNAPSHOT_OWNERSHIP,
    AuctionBid,
    AuctionBountyListing,
    AuctionSaleListing,
    Breed,
    Disease,
    DogName,
    EventOccurrence,
    GraveyardPooch,
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
    ServerEventOccurrence,
    ServerEventParticipation,
    StrayPooch,
    Vendor,
    VendorDesiredBreed,
    VendorDesiredMutation,
    VendorFirstName,
    VendorLastName,
    VendorPoochForSale,
)
from .session import session_scope
from .utils import rarity_choice

# Ordered rarity values from most common to most rare
_RARITY_ORDER = ["common", "uncommon", "novel", "rare", "unprecedented", "remarkable", "extraordinary", "unique"]

# Ordered health_impact values from most negative to most positive
_HEALTH_IMPACT_ORDER = [
    "instant_death",
    "fatal",
    "brutal",
    "severe",
    "unhealthy",
    "harmful",
    "neutral",
    "helpful",
    "healthy",
    "great",
    "fantastic",
    "brilliant",
    "immortality",
]


async def add_breed_to_pooch(
    pooch_id: int,
    breed_id: Optional[int] = None,
    weight: float = 0.5,
    rng: Optional[random.Random] = None,
    from_vendor: bool = False,
    from_ritual: bool = False,
    min_rarity: Optional[str] = None,
    max_rarity: Optional[str] = None,
) -> Optional[PoochBreed]:
    """
    Add the breed with the given ID to the pooch with the given ID.
    If a breed ID isn't given, choose a random one, with chance based on its rarity.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to add the breed to.

    breed_id: int, optional
        The ID of the breed to add to the pooch.

    weight: float, default : 0.5
        What fraction of the pooch's breed should be this breed.

    rng: Random, optional
        The random generator to use to determine the random breed, if `breed_id` is left blank.

    from_vendor: bool, default : False
        Specify whether this breed is being added from a vendor or not.
        This matters because some breeds can't show up on pooches sold by vendors.

    from_ritual: bool, default : False
        Specify whether this breed is being added from a bloodskull ritual or not.
        This matters because some breeds can't show up on pooches created by sacrificial rituals.

    min_rarity: str, optional
        The minimum rarity to allow when choosing randomly (inclusive).
        Uses rarity order: common → uncommon → novel → rare → unprecedented → remarkable → extraordinary → unique.

    max_rarity: str, optional
        The maximum rarity to allow when choosing randomly (inclusive).

    Returns
    -------
    PoochBreed, optional
        The PoochBreed relationship ORM object just created, or None if the breed was left to chance
        and the pooch already has EVERY breed.
    """

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:

        if breed_id is None:
            breed_query = select(Breed).where(
                Breed.id.not_in(select(PoochBreed.breed_id).where(PoochBreed.pooch_id == pooch_id))
            )
            if from_vendor:
                breed_query = breed_query.where(not_(Breed.parameters.contains({"sold_by_vendors": False})))
            if from_ritual:
                breed_query = breed_query.where(not_(Breed.parameters.contains({"born_from_ritual": False})))
            if min_rarity is not None and min_rarity.lower() in _RARITY_ORDER:
                min_idx = _RARITY_ORDER.index(min_rarity.lower())
                breed_query = breed_query.where(Breed.rarity.in_(_RARITY_ORDER[min_idx:]))
            if max_rarity is not None and max_rarity.lower() in _RARITY_ORDER:
                max_idx = _RARITY_ORDER.index(max_rarity.lower())
                breed_query = breed_query.where(Breed.rarity.in_(_RARITY_ORDER[: max_idx + 1]))

            breed_response = await session.execute(breed_query)
            rows = [(breed, breed.rarity) for breed in breed_response.scalars().all()]
            breed = rarity_choice(rng, rows)
            breed_id = breed.id if breed is not None else None

        # If the pooch somehow has every possible breed it's eligible for already...
        if breed_id is None:
            return None

        if weight >= 1.0:
            await session.execute(delete(PoochBreed).where(PoochBreed.pooch_id == pooch_id))
            pooch_breed = PoochBreed(pooch_id=pooch_id, breed_id=breed_id, weight=1)
            session.add(pooch_breed)
            await session.flush()
            return pooch_breed

        query = select(PoochBreed.breed_id, PoochBreed.weight).where(PoochBreed.pooch_id == pooch_id)
        response = await session.execute(query)
        existing = response.tuples().all()  # list of (breed_id, weight)
        existing_total = sum(w for _, w in existing)

        existing_breed_weight = next((w for bid, w in existing if bid == breed_id), 0)
        current_fraction = existing_breed_weight / existing_total if existing_total > 0 else 0.0
        combined_fraction = min(current_fraction + weight, 0.9999)

        others_total = existing_total - existing_breed_weight
        if others_total == 0:
            # Pooch only has this breed already; nothing to rescale.
            pooch_breed = await session.scalar(
                select(PoochBreed).where(PoochBreed.pooch_id == pooch_id, PoochBreed.breed_id == breed_id)
            )
            return pooch_breed

        # combined_fraction = target / (target + others_total)
        new_weight_raw = (combined_fraction / (1.0 - combined_fraction)) * others_total
        raw_weights = [(bid, w) for bid, w in existing if bid != breed_id] + [(breed_id, new_weight_raw)]
        raw_total = sum(w for _, w in raw_weights)

        # Drop any breed (except the one being added) that would be <1% of the total.
        raw_weights = [(bid, w) for bid, w in raw_weights if bid == breed_id or w / raw_total >= 0.01]
        min_raw = min(r for _, r in raw_weights)
        scaled = [(bid, max(round(r / min_raw), 1)) for bid, r in raw_weights]

        # Delete breeds that were pruned below the 1% threshold.
        surviving_ids = {bid for bid, _ in scaled}
        pruned_ids = [bid for bid, _ in existing if bid not in surviving_ids]
        if pruned_ids:
            await session.execute(
                delete(PoochBreed).where(PoochBreed.pooch_id == pooch_id, PoochBreed.breed_id.in_(pruned_ids))
            )

        breed_already_exists = existing_breed_weight > 0
        for scaled_breed_id, int_weight in scaled:
            if scaled_breed_id == breed_id:
                if breed_already_exists:
                    await session.execute(
                        update(PoochBreed)
                        .where(PoochBreed.pooch_id == pooch_id, PoochBreed.breed_id == scaled_breed_id)
                        .values(weight=int_weight)
                    )
                else:
                    pooch_breed = PoochBreed(pooch_id=pooch_id, breed_id=breed_id, weight=int_weight)
                    session.add(pooch_breed)
            else:
                await session.execute(
                    update(PoochBreed)
                    .where(PoochBreed.pooch_id == pooch_id, PoochBreed.breed_id == scaled_breed_id)
                    .values(weight=int_weight)
                )

        await session.flush()

        if breed_already_exists:
            pooch_breed = await session.scalar(
                select(PoochBreed).where(PoochBreed.pooch_id == pooch_id, PoochBreed.breed_id == breed_id)
            )

    return pooch_breed


async def add_mutation_to_pooch(
    pooch_id: int,
    mutation_id: Optional[int] = None,
    rng: Optional[random.Random] = None,
    from_vendor: bool = False,
    from_ritual: bool = False,
    min_rarity: Optional[str] = None,
    max_rarity: Optional[str] = None,
    min_health_impact: Optional[str] = None,
    max_health_impact: Optional[str] = None,
    exclude_mutation_ids: Optional[list[int]] = None,
    season: Optional[str] = None,
) -> Optional[PoochMutation]:
    """
    Add the mutation with the given ID to the pooch with the given ID.
    If a mutation ID isn't given, choose a random one, with chance based on its rarity.
    When `season` is provided (e.g. `"spring"`), mutations whose `parameters.seasons`
    list does not include that season are excluded from random selection (case-insensitive).
    Mutations with no `seasons` key are always eligible.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to add the mutation to.

    mutation_id: int, optional
        The ID of the mutation to add to the pooch.

    rng: Random, optional
        The random generator to use to determine the random mutation, if `mutation_id` is left blank.

    from_vendor: bool, default : False
        Specify whether this mutation is being added from a vendor or not.
        This matters because some mutations can't show up on pooches sold by vendors.

    from_ritual: bool, default : False
        Specify whether this mutation is being added from a bloodskull ritual or not.
        This matters because some mutations can't show up on pooches created by sacrificial rituals.

    min_rarity: str, optional
        Minimum rarity to allow when choosing randomly (inclusive).

    max_rarity: str, optional
        Maximum rarity to allow when choosing randomly (inclusive).

    min_health_impact: str, optional
        Minimum health_impact to allow when choosing randomly (inclusive).
        Order: instant_death → fatal → brutal → severe → unhealthy → harmful → neutral →
               helpful → healthy → great → fantastic → brilliant → immortality.

    max_health_impact: str, optional
        Maximum health_impact to allow when choosing randomly (inclusive).

    Returns
    -------
    PoochMutation
        The PoochMutation relationship ORM object just created, or None if the relation failed to create.
        Creation fails if the mutation is incompatible with existing ones, or the relation already exists.
    """

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:

        if mutation_id is None:
            mutation_query = (
                select(Mutation)
                .join(Pooch, Pooch.id == pooch_id)
                .where(
                    and_(
                        Mutation.id.not_in(select(PoochMutation.mutation_id).where(PoochMutation.pooch_id == pooch_id)),
                        or_(
                            and_(Pooch.sex == "male", Mutation.affects_males.is_(True)),
                            and_(Pooch.sex == "female", Mutation.affects_females.is_(True)),
                        ),
                    )
                )
            )
            if from_vendor:
                mutation_query = mutation_query.where(not_(Mutation.parameters.contains({"sold_by_vendors": False})))
            if from_ritual:
                mutation_query = mutation_query.where(not_(Mutation.parameters.contains({"born_from_ritual": False})))
            if min_rarity is not None and min_rarity.lower() in _RARITY_ORDER:
                min_idx = _RARITY_ORDER.index(min_rarity.lower())
                mutation_query = mutation_query.where(Mutation.rarity.in_(_RARITY_ORDER[min_idx:]))
            if max_rarity is not None and max_rarity.lower() in _RARITY_ORDER:
                max_idx = _RARITY_ORDER.index(max_rarity.lower())
                mutation_query = mutation_query.where(Mutation.rarity.in_(_RARITY_ORDER[: max_idx + 1]))
            if min_health_impact is not None and min_health_impact.lower() in _HEALTH_IMPACT_ORDER:
                min_idx = _HEALTH_IMPACT_ORDER.index(min_health_impact.lower())
                mutation_query = mutation_query.where(Mutation.health_impact.in_(_HEALTH_IMPACT_ORDER[min_idx:]))
            if max_health_impact is not None and max_health_impact.lower() in _HEALTH_IMPACT_ORDER:
                max_idx = _HEALTH_IMPACT_ORDER.index(max_health_impact.lower())
                mutation_query = mutation_query.where(Mutation.health_impact.in_(_HEALTH_IMPACT_ORDER[: max_idx + 1]))
            if exclude_mutation_ids:
                mutation_query = mutation_query.where(Mutation.id.not_in(exclude_mutation_ids))

            mutation_response = await session.execute(mutation_query)
            mutations = mutation_response.scalars().all()
            if season is not None:
                season_lower = season.lower()
                mutations = [
                    m
                    for m in mutations
                    if (
                        not m.parameters
                        or "seasons" not in m.parameters
                        or season_lower in [s.lower() for s in m.parameters["seasons"]]
                    )
                ]
            rows = [(m, m.rarity) for m in mutations]
            mutation = rarity_choice(rng, rows)
            mutation_id = mutation.id if mutation is not None else None

        # If the pooch somehow has every possible mutation already
        if mutation_id is None:
            return None

        existing_pooch_mutation = await session.scalar(
            select(PoochMutation).where(
                PoochMutation.pooch_id == pooch_id,
                PoochMutation.mutation_id == mutation_id,
            )
        )
        if existing_pooch_mutation is not None:
            return existing_pooch_mutation

        new_mutation = await session.scalar(select(Mutation).where(Mutation.id == mutation_id))
        if new_mutation is None:
            return None

        new_name = new_mutation.name
        new_incompatible_mutations: set[str] = set(new_mutation.parameters.get("incompatible_mutations", []))

        existing_mutations = (
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
        existing_names = {mutation.name for mutation in existing_mutations}

        # Check if the new mutation is incompatible with any existing ones
        if new_incompatible_mutations.intersection(existing_names):
            return None

        # Check if an existing mutation is incompatible with this new one
        for mutation in existing_mutations:
            incompatible_mutations: set[str] = set(mutation.parameters.get("incompatible_mutations", []))
            if new_name in incompatible_mutations:
                return None

        displayed_symptom = None
        if not new_mutation.visible and new_mutation.invisible_messages:
            displayed_symptom = rng.choice(new_mutation.invisible_messages)
        pooch_mutation = PoochMutation(
            pooch_id=pooch_id,
            mutation_id=mutation_id,
            displayed_symptom=displayed_symptom,
            visible=new_mutation.visible,
        )
        session.add(pooch_mutation)
        await session.flush()

    return pooch_mutation


async def add_injury_to_pooch(pooch_id: int, injury_id: int) -> Optional[PoochInjury]:
    """
    Add an injury to the given pooch.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to add the injury to.
    injury_id: int
        The ID of the injury to add.

    Returns
    -------
    PoochInjury, optional
        The newly created PoochInjury record, or None if the injury was not found.
    """
    async with session_scope() as session:
        injury = await session.get(Injury, injury_id)
        if injury is None:
            return None
        max_duplicates = (injury.parameters or {}).get("max_duplicates")
        if max_duplicates is not None:
            count_query = select(func.count()).where(
                and_(PoochInjury.pooch_id == pooch_id, PoochInjury.injury_id == injury_id)
            )
            existing_count = (await session.execute(count_query)).scalar_one()
            if existing_count >= max_duplicates:
                return None
        persistence = (injury.parameters or {}).get("persistence")
        displayed_symptom = None
        if not injury.visible and injury.invisible_messages:
            displayed_symptom = random.choice(injury.invisible_messages)
        pooch_injury = PoochInjury(
            pooch_id=pooch_id,
            injury_id=injury_id,
            persistence=persistence,
            displayed_symptom=displayed_symptom,
            visible=injury.visible,
        )
        session.add(pooch_injury)
        await session.flush()
    return pooch_injury


async def copy_pooch_injuries(source_id: int, dest_id: int) -> list[PoochInjury]:
    """
    Copy all PoochInjury records from source_id to dest_id, preserving every field
    (persistence, treated, last_treated_at, displayed_symptom, visible).
    """
    from .list import list_pooch_injury_instances

    instances = await list_pooch_injury_instances(source_id)
    copies: list[PoochInjury] = []
    async with session_scope() as session:
        for src in instances:
            new_injury = PoochInjury(
                pooch_id=dest_id,
                injury_id=src.injury_id,
                persistence=src.persistence,
                treated=src.treated,
                last_treated_at=src.last_treated_at,
                displayed_symptom=src.displayed_symptom,
                visible=src.visible,
            )
            session.add(new_injury)
            copies.append(new_injury)
        await session.flush()
    return copies


async def add_owner_to_server(server_discord_id: int, owner_discord_id: int) -> OwnerServer:
    """
    Add an owner with the given Discord ID to the server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to add the owner to.

    owner_discord_id: int
        The Discord ID of the owner to add to the server.

    Returns
    -------
    OwnerServer, optional
        The OwnerServer relationship ORM object just created.
    """

    async with session_scope() as session:
        owner_server = OwnerServer(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id)
        session.add(owner_server)
        await session.flush()

    return owner_server


async def add_pooch_breeds(pooch_id: int, breed_weights: dict[int, int]) -> list[PoochBreed]:
    """
    Bulk-set breeds for a pooch by inserting one PoochBreed row per breed id.
    Inteded for freshly created pooches. Does **not** delete existing breeds.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch.

    breed_weights: dict[int, int]
        Mapping of breed_id -> integer weight. Any non-positive weights are ignored.

    Returns
    -------
    list[PoochBreed]
        The created PoochBreed relationship rows.
    """

    rows: list[PoochBreed] = []
    async with session_scope() as session:
        for breed_id, weight in breed_weights.items():
            if weight is None or weight <= 0:
                continue
            row = PoochBreed(pooch_id=pooch_id, breed_id=breed_id, weight=weight)
            session.add(row)
            rows.append(row)
        await session.flush()

    return rows


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


async def add_pooch_to_vendor_stock(vendor_id: int, pooch_id: int) -> Optional[VendorPoochForSale]:
    """
    Add the pooch with the given ID to the given vendor's stock.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor whose stock the pooch will be added to.

    pooch_id: int
        The ID of the pooch to add to the given vendor's stock.

    Returns
    -------
    VendorPoochForSale, optional
        The VendorPoochForSale ORM object that was just created, or None if the vendor or pooch wasn't found.
    """

    vendor = await get_vendor_by_id(vendor_id)
    pooch = await get_pooch_by_id(pooch_id)

    if vendor is None or pooch is None:
        return None

    async with session_scope() as session:
        vendor_pooch_for_sale = VendorPoochForSale(vendor_id=vendor.id, pooch_id=pooch.id)
        session.add(vendor_pooch_for_sale)

    return vendor_pooch_for_sale


async def archive_active_event(active_owner_event_id: int, timed_out: bool = False) -> Optional[EventOccurrence]:
    """
    Archive an active event in place.

    Parameters
    ----------
    active_owner_event_id: int
        The ID of the active event to archive.

    timed_out: bool
        Whether the event timed out without a response.

    Returns
    -------
    EventOccurrence, optional
        The archived event occurrence, or None if the active event wasn't found.
    """

    async with session_scope() as session:
        query = select(EventOccurrence).where(
            EventOccurrence.id == active_owner_event_id, EventOccurrence.archived.is_(False)
        )
        result = await session.execute(query)
        active_event = result.scalar_one_or_none()

        if active_event is None:
            return None

        active_event.archived = True
        active_event.timed_out = timed_out
        active_event.completed_at = datetime.now(timezone.utc)
        await session.flush()

        return active_event


async def bury_pooch(owner_discord_id: int, pooch_id: int) -> Optional[GraveyardPooch]:
    """
    Move the given pooch to the given owner's graveyard.

    Parameters
    ----------
    owner_discord_id: int
        The ID of the owner whose graveyard the pooch will be added to.

    pooch_id: int
        The ID of the pooch to bury.

    Returns
    -------
    GraveyardPooch, optional
        The GraveyardPooch ORM object that was just created, or None if the pooch or owner wasn't found.
    """

    owner = await get_owner_by_discord_id(owner_discord_id)
    pooch = await get_pooch_by_id(pooch_id)

    if owner is None or pooch is None:
        return None

    async with session_scope() as session:
        graveyard_pooch = GraveyardPooch(owner_discord_id=owner.discord_id, pooch_id=pooch.id)
        session.add(graveyard_pooch)
        await session.flush()

    return graveyard_pooch


async def create_active_owner_event(
    event_id: int,
    owner_discord_id: int,
    context: dict[str, Any] = None,
    expires_at: Optional[datetime] = None,
) -> Optional[EventOccurrence]:
    """
    Create a new active event for an owner.

    Parameters
    ----------
    event_id: int
        The ID of the event that occurred.

    owner_discord_id: int
        The Discord ID of the owner the event occurred for.

    context: dict, optional
        Context about the event (affected pooches, etc.).

    expires_at: datetime, optional
        When the event expires if not responded to.

    Returns
    -------
    EventOccurrence, optional
        The created EventOccurrence, or None if creation failed.
    """

    if context is None:
        context = {}

    async with session_scope() as session:
        active_event = EventOccurrence(
            event_id=event_id,
            owner_discord_id=owner_discord_id,
            context=context,
            triggered_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            archived=False,
        )
        session.add(active_event)
        await session.flush()

        query = (
            select(EventOccurrence)
            .where(EventOccurrence.id == active_event.id, EventOccurrence.archived.is_(False))
            .options(selectinload(EventOccurrence.event))
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def create_kennel(
    owner_discord_id: int, name: str = "Kennel", pooch_limit: int = KENNEL_POOCH_LIMIT
) -> Optional[Kennel]:
    """
    Create a kennel for the given owner.

    Parameters
    ----------
    owner_discord_id: int
        The discord ID of the owner to create the kennel for.

    name: str, default : "Kennel"
        The name to give the new kennel.

    pooch_limit: int, default : `KENNEL_POOCH_LIMIT`
        The size limit to give the new kennel.

    Returns
    -------
    Kennel, optional
        The newly created Kennel, or None if the owner with the given Discord ID couldn't be found.
    """

    owner = await get_owner_by_discord_id(owner_discord_id)

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


async def create_owner(owner_discord_id: int) -> Owner:
    """
    Create an owner with the given Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to create.

    Returns
    -------
    Owner
        The Owner ORM object just created.
    """

    async with session_scope() as session:
        owner = Owner(discord_id=owner_discord_id)
        session.add(owner)
        await session.flush()

    return owner


async def create_pooch(
    owner_discord_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    name: Optional[str] = None,
    sex: Optional[str] = None,
    age: int = POOCH_FETAL_AGE,
    base_health: int = POOCH_BASE_HEALTH,
    strength: int = POOCH_STAT_DEFAULT,
    cuteness: int = POOCH_STAT_DEFAULT,
    fluffiness: int = POOCH_STAT_DEFAULT,
    intelligence: int = POOCH_STAT_DEFAULT,
    dexterity: int = POOCH_STAT_DEFAULT,
    fertility: int = POOCH_STAT_DEFAULT,
    aggressiveness: int = POOCH_STAT_DEFAULT,
    constitution: int = POOCH_STAT_DEFAULT,
    breeding_cooldown: int = POOCH_BREEDING_COOLDOWN,
    size: Optional[int] = None,
    breeds: Optional[list[int | str]] = None,
    mutations: Optional[list[int | str]] = None,
    rng: Optional[random.Random] = None,
) -> Pooch:
    """
    Create a pooch, optionally assigning breeds and mutations in the same operation.

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

    age: int, default : `POOCH_FETAL_AGE`
        The age to make the pooch. Defaults to the fetal age.

    base_health: int, default : `POOCH_BASE_HEALTH`
        The base health to give the pooch. Defaults to the base average pooch health.

    breeding_cooldown: int, default : `POOCH_BREEDING_COOLDOWN`
        The breeding cooldown to start the pooch off with. Defaults to the base breeding cooldown.

    size: int, optional
        An explicit size to give the pooch. If not provided and breeds are given, size is computed
        as a random value within the weighted-average min/max size bounds of the breeds.
        If no breeds are given either, defaults to POOCH_STAT_DEFAULT.

    breeds: list[int | str], optional
        Breeds to assign to the pooch. Each entry is either a breed ID (int) or breed name (str).
        Duplicates are allowed and increase the relative weight of that breed by 1 per occurrence.
        Unresolvable entries are silently skipped.

    mutations: list[int | str], optional
        Mutations to assign to the pooch. Each entry is a mutation ID (int) or mutation name (str).
        Duplicate entries are deduplicated — a pooch cannot have the same mutation twice.
        Unresolvable entries are silently skipped.

    rng: Random, optional
        The random generator to determine randomness, if any pooch traits are left to chance (name, sex, size).

    Returns
    -------
    Pooch
        The Pooch ORM object that was just created.
    """

    rng = rng if rng is not None else random.Random()

    async def _get_random_pooch_name(session) -> str:
        statement = select(DogName).order_by(func.hashtextextended(DogName.name, bindparam("seed"))).limit(1)
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        dog_name = response.scalar_one_or_none()
        return dog_name.name if dog_name is not None else "Dog"

    def _get_random_sex():
        return "female" if rng.randint(0, 1) == 0 else "male"

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
        # Resolve breeds: build {breed_id: weight} where weight = occurrence count
        breed_weights: dict[int, int] = {}
        resolved_breed_objects: list[Breed] = []
        if breeds:
            for entry in breeds:
                if isinstance(entry, int):
                    row = await session.scalar(select(Breed).where(Breed.id == entry))
                elif isinstance(entry, str):
                    row = await session.scalar(select(Breed).where(Breed.name.ilike(entry)))
                else:
                    row = None
                if row is not None:
                    breed_weights[row.id] = breed_weights.get(row.id, 0) + 1
                    if row.id not in {b.id for b in resolved_breed_objects}:
                        resolved_breed_objects.append(row)

        # Compute size from breed bounds if not explicitly provided
        if size is None:
            if resolved_breed_objects:
                total_weight = sum(breed_weights[b.id] for b in resolved_breed_objects)
                avg_min = round(sum(b.min_size * breed_weights[b.id] for b in resolved_breed_objects) / total_weight)
                avg_max = round(sum(b.max_size * breed_weights[b.id] for b in resolved_breed_objects) / total_weight)
                size = rng.randint(avg_min, avg_max) if avg_min <= avg_max else avg_min
            else:
                size = POOCH_STAT_DEFAULT

        # Resolve mutations: deduplicate, skip unknown
        mutation_ids: list[int] = []
        seen_mutation_ids: set[int] = set()
        if mutations:
            for entry in mutations:
                if isinstance(entry, int):
                    row = await session.scalar(select(Mutation).where(Mutation.id == entry))
                elif isinstance(entry, str):
                    row = await session.scalar(select(Mutation).where(Mutation.name.ilike(entry)))
                else:
                    row = None
                if row is not None and row.id not in seen_mutation_ids:
                    seen_mutation_ids.add(row.id)
                    mutation_ids.append(row.id)

        pooch_name = name or await _get_random_pooch_name(session)
        pooch_sex = sex or _get_random_sex()

        pooch = Pooch(
            owner_discord_id=owner_discord_id,
            vendor_id=vendor_id,
            name=pooch_name,
            sex=pooch_sex,
            age=age,
            base_health=base_health,
            health_loss_age=POOCH_HEALTH_LOSS_AGE,
            strength=strength,
            cuteness=cuteness,
            fluffiness=fluffiness,
            intelligence=intelligence,
            dexterity=dexterity,
            fertility=fertility,
            aggressiveness=aggressiveness,
            constitution=constitution,
            size=size,
            breeding_cooldown=breeding_cooldown,
            alive=True,
            virgin=True,
        )
        session.add(pooch)
        await session.flush()

        for breed_id, weight in breed_weights.items():
            session.add(PoochBreed(pooch_id=pooch.id, breed_id=breed_id, weight=weight))
        for mutation_id in mutation_ids:
            session.add(PoochMutation(pooch_id=pooch.id, mutation_id=mutation_id))

        await session.flush()

        # Birth snapshot: only created for pooches born at age >= 0.
        # Pooches created at age -1 (fetuses) get their birth snapshot when they are
        # aged from -1 to 0 during the daily day-change cycle.
        if age >= 0:
            from datetime import timedelta

            birth_time = datetime.now(timezone.utc) - timedelta(days=age)
            session.add(
                PoochSnapshot(
                    pooch_id=pooch.id,
                    kind=SNAPSHOT_BIRTH,
                    description=f"{pooch.name} was born.",
                    snapshot_at=birth_time,
                )
            )
            await session.flush()

    return pooch


async def create_pooch_pregnancy(mother_id: int, fetus_id: int) -> PoochPregnancy:
    """
    Create a pregnancy relationship between a mother and fetus.

    Parameters
    ----------
    mother_id: int
        The ID of the mother pooch.

    fetus_id: int
        The ID of the fetus pooch.

    Returns
    -------
    PoochPregnancy
        The ORM PoochPregnancy object just created.
    """

    async with session_scope() as session:
        pregnancy = PoochPregnancy(mother_id=mother_id, fetus_id=fetus_id)
        session.add(pregnancy)
        await session.flush()

    return pregnancy


async def create_server(server_discord_id: int) -> Server:
    """
    Create a server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to create.

    Returns
    -------
    Server
        The Server ORM object just created.
    """

    async with session_scope() as session:
        server = Server(discord_id=server_discord_id)
        session.add(server)
        await session.flush()

    return server


async def create_vendor(
    server_discord_id: int,
    name: Optional[str] = None,
    price_markup: float = VENDOR_PRICE_MARKUP,
    rng: Optional[random.Random] = None,
) -> Optional[Vendor]:
    """
    Create a vendor in the given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to create the vendor in.

    name: str, optional
        The name to give the new vendor. Chooses a random one if not given.

    price_markup: float, default : `VENDOR_PRICE_MARKUP`
        The markup to multiply the buying price of any pooches the vendor is selling by.

    rng: Random, optional
        The random generator to determine randomness, if any vendor traits are left to chance (name, desired mutations).

    Returns
    -------
    Vendor, optional
        The Vendor ORM object that was just created, or None if the server with the given ID wasn't found.
    """

    rng = rng if rng is not None else random.Random()

    # All distinct rarity tiers in the game
    _ALL_RARITIES = ["common", "uncommon", "novel", "rare", "unprecedented", "remarkable", "extraordinary", "unique"]

    async def _get_random_vendor_name() -> str:
        statement = (
            select(VendorFirstName).order_by(func.hashtextextended(VendorFirstName.name, bindparam("seed"))).limit(1)
        )
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        first_name = response.scalar_one_or_none()

        statement = (
            select(VendorLastName).order_by(func.hashtextextended(VendorLastName.name, bindparam("seed"))).limit(1)
        )
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        last_name = response.scalar_one_or_none()

        return (
            f"{(first_name.name + ' ') if first_name is not None else ''}"
            f"{last_name.name if last_name is not None else ''}"
        )

    async def _get_unique_random_mutation_ids(count: int) -> list[int]:
        """Pick `count` distinct mutation IDs by shuffling all IDs with a seed."""
        statement = select(Mutation.id).order_by(func.hashtextextended(Mutation.name, bindparam("seed"))).limit(count)
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        return list(response.scalars().all())

    async def _get_random_breed_id_for_rarity(rarity: str) -> Optional[int]:
        statement = (
            select(Breed.id)
            .where(Breed.rarity == rarity)
            .order_by(func.hashtextextended(Breed.name, bindparam("seed")))
            .limit(1)
        )
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        return response.scalar_one_or_none()

    async with session_scope() as session:
        vendor = Vendor(
            server_discord_id=server_discord_id,
            name=name or await _get_random_vendor_name(),
            price_markup=price_markup,
        )
        session.add(vendor)
        await session.flush()

        # Assign 2–5 unique desired mutations
        mutation_count = rng.randint(*VENDOR_DESIRED_MUTATION_COUNT_RANGE)
        mutation_ids = await _get_unique_random_mutation_ids(mutation_count)
        for mutation_id in mutation_ids:
            session.add(VendorDesiredMutation(vendor_id=vendor.id, mutation_id=mutation_id))

        # Assign exactly one desired breed per rarity tier
        for rarity in _ALL_RARITIES:
            breed_id = await _get_random_breed_id_for_rarity(rarity)
            if breed_id is not None:
                session.add(VendorDesiredBreed(vendor_id=vendor.id, breed_id=breed_id))

        await session.flush()

    return vendor


async def damn_pooch(pooch_id: int) -> Optional[HellPooch]:
    """
    Move the given pooch to Hell, removing it from any kennel, stray pool, or graveyard first.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to damn.

    Returns
    -------
    HellPooch, optional
        The HellPooch ORM object that was just created, or None if the pooch wasn't found.
    """

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return None

    async with session_scope() as session:
        # Remove from kennel if present
        kennel_row = (
            await session.execute(select(KennelPooch).where(KennelPooch.pooch_id == pooch_id))
        ).scalar_one_or_none()
        if kennel_row is not None:
            await session.delete(kennel_row)

        # Remove from strays if present
        stray_row = await session.get(StrayPooch, pooch_id)
        if stray_row is not None:
            await session.delete(stray_row)

        # Remove from graveyard if present
        grave_row = (
            await session.execute(select(GraveyardPooch).where(GraveyardPooch.pooch_id == pooch_id))
        ).scalar_one_or_none()
        if grave_row is not None:
            await session.delete(grave_row)

        # Only add to hell if not already there
        existing_hell = await session.get(HellPooch, pooch_id)
        if existing_hell is None:
            hell_pooch = HellPooch(pooch_id=pooch.id)
            session.add(hell_pooch)
            await session.flush()
            return hell_pooch

    return existing_hell


async def revive_pooch(pooch_id: int) -> Optional[Pooch]:
    """
    Revive a pooch — sets alive=True and removes it from hell or graveyard if present.
    Does not place the pooch anywhere; the caller is responsible for routing.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to revive.

    Returns
    -------
    Pooch, optional
        The updated Pooch ORM object, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        pooch = (await session.execute(select(Pooch).where(Pooch.id == pooch_id))).scalar_one_or_none()
        if pooch is None:
            return None

        pooch.alive = True

        hell_row = await session.get(HellPooch, pooch_id)
        if hell_row is not None:
            await session.delete(hell_row)

        grave_row = (
            await session.execute(select(GraveyardPooch).where(GraveyardPooch.pooch_id == pooch_id))
        ).scalar_one_or_none()
        if grave_row is not None:
            await session.delete(grave_row)

        await session.flush()

    return pooch


async def set_pooch_parentage(child_id: int, father_id: int | None, mother_id: int | None) -> PoochParentage:
    """
    Set the parentage for a child pooch.

    Parameters
    ----------
    child_id: int
        The ID of the child.

    father_id: int | None
        The ID of the father, if known.

    mother_id: int | None
        The ID of the mother, if known.

    Returns
    -------
    PoochParentage
        The created relationship row.
    """

    async with session_scope() as session:
        parentage = PoochParentage(child_id=child_id, father_id=father_id, mother_id=mother_id)
        session.add(parentage)
        await session.flush()

    return parentage


async def create_server_event_occurrence(
    server_discord_id: int,
    server_event_id: int,
    context: dict[str, Any],
    expires_at: datetime,
) -> ServerEventOccurrence:
    """
    Create server event occurrence.

    Parameters
    ----------
    server_discord_id: Any
        The `server_discord_id` value.

    server_event_id: Any
        The `server_event_id` value.

    context: Any
        The `context` value.

    expires_at: Any
        The `expires_at` value.

    Returns
    -------
    Any
        The result of calling `create_server_event_occurrence`.
    """

    async with session_scope() as session:
        occurrence = ServerEventOccurrence(
            server_discord_id=server_discord_id,
            server_event_id=server_event_id,
            context=context,
            expires_at=expires_at,
        )
        session.add(occurrence)
        await session.flush()
        await session.refresh(occurrence)
    return occurrence


async def add_pooch_to_strays(pooch_id: int, server_discord_id: int) -> Optional[StrayPooch]:
    """
    Move the given pooch to the stray pool for the given server.
    Removes the pooch from its kennel (if any), clears its owner and vendor, then inserts a StrayPooch row.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to make a stray.

    server_discord_id: int
        The Discord ID of the server the stray will belong to.

    Returns
    -------
    StrayPooch, optional
        The StrayPooch ORM object just created, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        pooch = await session.get(Pooch, pooch_id)
        if pooch is None:
            return None
        pooch.owner_discord_id = None
        pooch.vendor_id = None
        kennel_row = await session.get(KennelPooch, pooch_id)
        if kennel_row:
            await session.delete(kennel_row)
        stray = StrayPooch(pooch_id=pooch_id, server_discord_id=server_discord_id)
        session.add(stray)
        session.add(
            PoochSnapshot(
                pooch_id=pooch_id,
                kind=SNAPSHOT_OWNERSHIP,
                description=f"{pooch.name} became a stray.",
                snapshot_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()
        return stray


async def create_server_event_participation(
    occurrence_id: int,
    owner_discord_id: int,
    context: dict[str, Any],
    first_submission: dict[str, Any],
    immediate_result: dict[str, Any],
) -> ServerEventParticipation:
    """
    Create server event participation.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    owner_discord_id: Any
        The `owner_discord_id` value.

    context: Any
        The `context` value.

    first_submission: Any
        The `first_submission` value.

    immediate_result: Any
        The `immediate_result` value.

    Returns
    -------
    Any
        The result of calling `create_server_event_participation`.
    """

    async with session_scope() as session:
        participation = ServerEventParticipation(
            occurrence_id=occurrence_id,
            owner_discord_id=owner_discord_id,
            context=context,
            submissions=[first_submission],
            immediate_result=immediate_result,
        )
        session.add(participation)
        await session.flush()
        await session.refresh(participation)
    return participation


async def create_pooch_snapshot(
    pooch_id: int,
    kind: str,
    description: str,
    snapshot_at: Optional[datetime] = None,
    entity_ids: Optional[list[int]] = None,
) -> PoochSnapshot:
    """
    Record a timeline snapshot for a pooch.

    Parameters
    ----------
    pooch_id: int
        ID of the pooch this snapshot belongs to.
    kind: str
        One of the SNAPSHOT_* constants (birth, death, ownership, vet_injuries, vet_mutations).
    description: str
        Human-readable description of the event.
    snapshot_at: datetime
        The timestamp of the event (timezone-aware).
    entity_ids: list[int], optional
        Optional list of injury or mutation IDs captured at the time (vet snapshots).
    """
    async with session_scope() as session:
        snapshot = PoochSnapshot(
            pooch_id=pooch_id,
            kind=kind,
            description=description,
            snapshot_at=snapshot_at or datetime.now(timezone.utc),
            entity_ids=entity_ids or None,
        )
        session.add(snapshot)
        await session.flush()
    return snapshot


async def append_server_event_submission(
    participation_id: int,
    submission: dict[str, Any],
) -> None:
    """Append a new submission dict to an existing participation's submissions list."""
    from sqlalchemy import update as sa_update

    async with session_scope() as session:
        # Use jsonb_append via raw expression to avoid read-modify-write race;
        # for our single-server-per-guild architecture this is safe with a simple refresh approach.
        participation = await session.get(ServerEventParticipation, participation_id)
        if participation is not None:
            current: list = list(participation.submissions or [])
            current.append(submission)
            await session.execute(
                sa_update(ServerEventParticipation)
                .where(ServerEventParticipation.id == participation_id)
                .values(submissions=current)
            )


async def create_auction_sale_listing(
    pooch_id: int,
    seller_discord_id: int,
    server_discord_id: int,
    minimum_bid: int,
    expires_at: Optional[datetime] = None,
) -> AuctionSaleListing:
    """Create a new active auction sale listing for the given pooch."""
    async with session_scope() as session:
        listing = AuctionSaleListing(
            pooch_id=pooch_id,
            seller_discord_id=seller_discord_id,
            server_discord_id=server_discord_id,
            minimum_bid=minimum_bid,
            expires_at=expires_at,
        )
        session.add(listing)
        await session.flush()
    return listing


async def create_auction_bid(
    listing_id: int,
    bidder_discord_id: int,
    amount: int,
) -> AuctionBid:
    """Insert a new bid row for the given listing."""
    async with session_scope() as session:
        bid = AuctionBid(
            listing_id=listing_id,
            bidder_discord_id=bidder_discord_id,
            amount=amount,
        )
        session.add(bid)
        await session.flush()
    return bid


async def create_auction_bounty_listing(
    buyer_discord_id: int,
    server_discord_id: int,
    title: str,
    escrow_amount: int,
    criteria: list,
) -> AuctionBountyListing:
    """Create a new active bounty listing. Does NOT deduct escrow — caller handles that."""
    async with session_scope() as session:
        listing = AuctionBountyListing(
            buyer_discord_id=buyer_discord_id,
            server_discord_id=server_discord_id,
            title=title,
            escrow_amount=escrow_amount,
            criteria=criteria,
        )
        session.add(listing)
        await session.flush()
    return listing


async def add_disease_to_pooch(
    pooch_id: int,
    disease_id: int,
    current_day: int = 0,
    rng: Optional[random.Random] = None,
) -> Optional[PoochDisease]:
    """
    Give a pooch a disease. Sets invisible state based on disease visibility settings.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to add the disease to.
    disease_id: int
        The ID of the disease to add.
    current_day: int
        The current global day number, stored as contracted_day.
    rng: Random, optional
        The random generator to use for invisible message selection.

    Returns
    -------
    PoochDisease, optional
        The newly created PoochDisease record, or None if the disease was not found.
    """
    rng = rng if rng is not None else random.Random()
    async with session_scope() as session:
        disease = await session.get(Disease, disease_id)
        if disease is None:
            return None
        existing = await session.scalar(
            select(PoochDisease).where(PoochDisease.pooch_id == pooch_id, PoochDisease.disease_id == disease_id)
        )
        if existing is not None:
            return existing
        displayed_symptom = None
        if not disease.visible and disease.invisible_messages:
            displayed_symptom = rng.choice(disease.invisible_messages)
        pooch_disease = PoochDisease(
            pooch_id=pooch_id,
            disease_id=disease_id,
            contracted_day=current_day,
            displayed_symptom=displayed_symptom,
            visible=disease.visible,
        )
        session.add(pooch_disease)
        await session.flush()
    return pooch_disease


async def add_disease_immunity_to_pooch(
    pooch_id: int,
    disease_id: int,
    immune_until_day: int,
) -> Optional[PoochDiseaseImmunity]:
    """
    Grant a pooch immunity to a disease until the given day.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to grant immunity to.
    disease_id: int
        The ID of the disease to grant immunity against.
    immune_until_day: int
        The day number when the immunity expires.

    Returns
    -------
    PoochDiseaseImmunity, optional
        The newly created PoochDiseaseImmunity record.
    """
    async with session_scope() as session:
        immunity = await session.scalar(
            select(PoochDiseaseImmunity).where(
                PoochDiseaseImmunity.pooch_id == pooch_id,
                PoochDiseaseImmunity.disease_id == disease_id,
            )
        )
        if immunity is None:
            immunity = PoochDiseaseImmunity(
                pooch_id=pooch_id,
                disease_id=disease_id,
                immune_until_day=immune_until_day,
            )
            session.add(immunity)
        else:
            immunity.immune_until_day = max(immunity.immune_until_day, immune_until_day)
        await session.flush()
    return immunity
