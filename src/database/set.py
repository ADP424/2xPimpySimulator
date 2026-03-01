import random
from typing import Optional, TypeVar

from sqlalchemy import and_, bindparam, delete, func, not_, or_, select

from .constants import (
    KENNEL_POOCH_LIMIT,
    POOCH_BASE_HEALTH,
    POOCH_BREEDING_COOLDOWN,
    POOCH_FETAL_AGE,
    POOCH_HEALTH_LOSS_AGE,
    RANDOM_SEED_SIZE_LIMIT,
    VENDOR_PRICE_MARKUP,
)
from .get import get_owner_by_discord_id, get_pooch_by_id, get_vendor_by_id
from .models import (
    Breed,
    DogName,
    GraveyardPooch,
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
    RarityWeight,
    Server,
    Vendor,
    VendorFirstName,
    VendorLastName,
    VendorPoochForSale,
)
from .session import session_scope

T = TypeVar("T")


def _weighted_choice(rng: random.Random, items: list[tuple[T, int]]) -> Optional[T]:
    if len(items) == 0:
        return None

    total = sum(weight for _, weight in items)
    roll = rng.uniform(0, total)

    accumulated = 0
    for item, weight in items:
        accumulated += weight
        if roll <= accumulated:
            return item


async def add_breed_to_pooch(
    pooch_id: int,
    breed_id: Optional[int] = None,
    weight: float = 0.5,
    rng: Optional[random.Random] = None,
    from_vendor: bool = False,
    from_ritual: bool = False,
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

    Returns
    -------
    PoochBreed, optional
        The PoochBreed relationship ORM object just created, or None if the breed was left to chance
        and the pooch already has EVERY breed.
    """

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:

        if breed_id is None:
            breed_query = (
                select(Breed, RarityWeight.weight)
                .join(RarityWeight, RarityWeight.rarity == Breed.rarity)
                .where(Breed.id.not_in(select(PoochBreed.breed_id).where(PoochBreed.pooch_id == pooch_id)))
            )
            if from_vendor:
                breed_query = breed_query.where(not_(Breed.advanced_options.contains({"sold_by_vendors": 0})))
            if from_ritual:
                breed_query = breed_query.where(not_(Breed.advanced_options.contains({"born_from_ritual": 0})))

            breed_response = await session.execute(breed_query)
            rows = [(breed, breed_weight) for breed, breed_weight in breed_response.tuples().all()]
            breed = _weighted_choice(rng, rows)
            breed_id = breed.id if breed is not None else None

        # If the pooch somehow has every possible breed it's eligible for already
        if breed_id is None:
            return None

        existing_pooch_breed = await session.scalar(
            select(PoochBreed).where(
                PoochBreed.pooch_id == pooch_id,
                PoochBreed.breed_id == breed_id,
            )
        )
        if existing_pooch_breed is not None:
            return existing_pooch_breed

        if weight >= 1.0:
            await session.execute(delete(PoochBreed).where(PoochBreed.pooch_id == pooch_id))
            pooch_breed = PoochBreed(
                pooch_id=pooch_id,
                breed_id=breed_id,
                weight=1,
            )
            session.add(pooch_breed)
            await session.flush()
            return pooch_breed

        query = select(PoochBreed.weight).where(PoochBreed.pooch_id == pooch_id)
        response = await session.execute(query)
        total_weight = sum(response.scalars().all())
        pooch_breed = PoochBreed(
            pooch_id=pooch_id, breed_id=breed_id, weight=max(round((weight / (1.0 - weight)) * total_weight), 1)
        )
        session.add(pooch_breed)
        await session.flush()

    return pooch_breed


async def add_mutation_to_pooch(
    pooch_id: int, mutation_id: Optional[int] = None, rng: Optional[random.Random] = None
) -> Optional[PoochMutation]:
    """
    Add the mutation with the given ID to the pooch with the given ID.
    If a mutation ID isn't given, choose a random one, with chance based on its rarity.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to add the mutation to.

    mutation_id: int, optional
        The ID of the mutation to add to the pooch.

    rng: Random, optional
        The random generator to use to determine the random mutation, if `mutation_id` is left blank.

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
                select(Mutation, RarityWeight.weight)
                .join(RarityWeight, RarityWeight.rarity == Mutation.rarity)
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
            mutation_response = await session.execute(mutation_query)
            rows = [(mutation, weight) for mutation, weight in mutation_response.tuples().all()]
            mutation = _weighted_choice(rng, rows)
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
        new_incompatible_mutations: set[str] = set(new_mutation.advanced_options.get("incompatible_mutations", []))

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
            incompatible_mutations: set[str] = set(mutation.advanced_options.get("incompatible_mutations", []))
            if new_name in incompatible_mutations:
                return None

        pooch_mutation = PoochMutation(pooch_id=pooch_id, mutation_id=mutation_id)
        session.add(pooch_mutation)
        await session.flush()

    return pooch_mutation


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
            if weight is None or int(weight) <= 0:
                continue
            row = PoochBreed(pooch_id=pooch_id, breed_id=int(breed_id), weight=int(weight))
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
    breeding_cooldown: int = POOCH_BREEDING_COOLDOWN,
    rng: Optional[random.Random] = None,
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

    age: int, default : `POOCH_FETAL_AGE`
        The age to make the pooch. Defaults to the fetal age.

    base_health: int, default : `POOCH_BASE_HEALTH`
        The base health to give the pooch. Defaults to the base average pooch health.

    breeding_cooldown: int, default : `POOCH_BREEDING_COOLDOWN`
        The breeding cooldown to start the pooch off with. Defaults to the base breeding cooldown.

    rng: Random, optional
        The random generator to determine randomness, if any pooch traits are left to chance (name, sex).

    Returns
    -------
    Pooch
        The Pooch ORM object that was just created.
    """

    rng = rng if rng is not None else random.Random()

    async def _get_random_pooch_name() -> str:
        statement = select(DogName).order_by(func.hashtextextended(DogName.name, bindparam("seed"))).limit(1)
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        dog_name = response.scalar_one_or_none()
        return dog_name.name if dog_name is not None else "Dog"

    async def _get_random_sex():
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
        pooch = Pooch(
            owner_discord_id=owner_discord_id,
            vendor_id=vendor_id,
            name=name or await _get_random_pooch_name(),
            sex=sex or await _get_random_sex(),
            age=age,
            base_health=base_health,
            health_loss_age=POOCH_HEALTH_LOSS_AGE,
            breeding_cooldown=breeding_cooldown,
            alive=True,
            virgin=True,
        )
        session.add(pooch)
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

    async def _get_random_mutation_id() -> Optional[int]:
        statement = select(Mutation.id).order_by(func.hashtextextended(Mutation.name, bindparam("seed"))).limit(1)
        response = await session.execute(statement, {"seed": rng.randint(0, RANDOM_SEED_SIZE_LIMIT)})
        mutation = response.scalar_one_or_none()
        return mutation

    async with session_scope() as session:
        vendor = Vendor(
            server_discord_id=server_discord_id,
            name=name or await _get_random_vendor_name(),
            price_markup=price_markup,
            desired_mutation_1=(await _get_random_mutation_id()),
            desired_mutation_2=(await _get_random_mutation_id()),
            desired_mutation_3=(await _get_random_mutation_id()),
        )
        session.add(vendor)
        await session.flush()

    return vendor


async def damn_pooch(pooch_id: int) -> Optional[HellPooch]:
    """
    Move the given pooch to Hell.

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
        hell_pooch = HellPooch(pooch_id=pooch.id)
        session.add(hell_pooch)
        await session.flush()

    return hell_pooch


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
