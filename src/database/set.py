import random
from typing import Optional, TypeVar

from sqlalchemy import bindparam, func, select

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

# from .models import *  # loads all ORM models (via database/models/__init__.py)
from .models import (
    Breed,
    DogName,
    GraveyardPooch,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    OwnerServer,
    Pooch,
    PoochBreed,
    PoochMutation,
    RarityWeight,
    Server,
    Vendor,
    VendorFirstName,
    VendorLastName,
    VendorPoochForSale,
)
from .session import session_scope

T = TypeVar("T")


async def create_pooch(
    owner_discord_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    name: Optional[str] = None,
    sex: Optional[str] = None,
    age: int = POOCH_FETAL_AGE,
    base_health: int = POOCH_BASE_HEALTH,
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
        The base health to give the pooch. Chooses randomly within a range if not given.

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
            breeding_cooldown=POOCH_BREEDING_COOLDOWN,
            alive=True,
            virgin=True,
        )
        session.add(pooch)
        await session.flush()

    return pooch


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
    pooch_id: int, breed_id: Optional[int] = None, weight: float = 0.5, rng: Optional[random.Random] = None
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
            breed_response = await session.execute(breed_query)
            rows = [(breed, weight) for breed, weight in breed_response.tuples().all()]
            breed = _weighted_choice(rng, rows)
            breed_id = breed.id if breed is not None else None

        # If the pooch somehow has every possible breed already
        if breed_id is None:
            return None

        query = (
            select(RarityWeight.weight)
            .join(Breed, Breed.rarity == RarityWeight.rarity)
            .join(PoochBreed, PoochBreed.breed_id == Breed.id)
            .where(PoochBreed.pooch_id == pooch_id)
        )
        response = await session.execute(query)
        total_weight = sum(response.scalars().all())
        pooch_breed = PoochBreed(pooch_id=pooch_id, breed_id=breed_id, weight=max(round(2 * weight * total_weight), 1))
        session.add(pooch_breed)
        await session.flush()

    return pooch_breed


async def add_mutation_to_pooch(
    pooch_id: int, mutation_id: Optional[int] = None, rng: Optional[random.Random] = None
) -> PoochMutation:
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
        The PoochMutation relationship ORM object just created.
    """

    rng = rng if rng is not None else random.Random()

    async with session_scope() as session:

        if mutation_id is None:
            mutation_query = (
                select(Mutation, RarityWeight.weight)
                .join(RarityWeight, RarityWeight.rarity == Mutation.rarity)
                .where(Mutation.id.not_in(select(PoochMutation.mutation_id).where(PoochMutation.pooch_id == pooch_id)))
            )
            mutation_response = await session.execute(mutation_query)
            rows = [(mutation, weight) for mutation, weight in mutation_response.tuples().all()]
            mutation = _weighted_choice(rng, rows)
            mutation_id = mutation.id if mutation is not None else None

        # If the pooch somehow has every possible mutation already
        if mutation_id is None:
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
