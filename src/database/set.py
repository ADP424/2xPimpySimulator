import random
from typing import Optional
from sqlalchemy import cast, func, select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)
from .models.enums.sex import SEX

from .get import get_owner_by_discord_id, get_vendor_by_id, get_pooch_by_id


async def create_pooch(
    owner_discord_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    name: Optional[str] = None,
    sex: Optional[str] = None,
    age: int = -1,
    base_health: Optional[int] = None,
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

    age: int, default = -1
        The age to make the pooch. Defaults to -1 (fetal age).

    base_health: int, optional
        The base health to give the pooch. Chooses randomly within a range if not given.

    Returns
    -------
    Pooch
        The Pooch ORM object that was just created.
    """

    async def _get_random_pooch_name():
        statement = select(DogName).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        dog_name = response.scalar_one_or_none()
        return dog_name.name if dog_name is not None else "Dog"

    async def _get_random_sex():
        statement = select(func.unnest(func.enum_range(cast(None, SEX)))).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        s = response.scalar_one_or_none()
        return s if s is not None else "female"

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
            base_health=base_health or random.randint(8, 12),  # TODO
            health_loss_age=0,  # TODO
            breeding_cooldown=2,  # TODO
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


async def create_kennel(owner_discord_id: int, name: str = "Kennel", pooch_limit: int = 10) -> Optional[Kennel]:  # TODO
    """
    Create a kennel for the given owner.

    Parameters
    ----------
    owner_discord_id: int
        The discord ID of the owner to create the kennel for.

    name: str, default: "Kennel"
        The name to give the new kennel.

    pooch_limit: int, default: 10
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


async def create_vendor(server_discord_id: int, name: Optional[str] = None) -> Optional[Vendor]:
    """
    Fetch the list of vendors for a given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to create the vendor in.

    name: str, optional
        The name to give the new vendor. Chooses a random one if not given.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object that was just created, or None if the server with the given ID wasn't found.
    """

    async def _get_random_vendor_name():
        statement = select(VendorFirstName).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        first_name = response.scalar_one_or_none()

        statement = select(VendorLastName).order_by(func.random()).limit(1)
        response = await session.execute(statement)
        last_name = response.scalar_one_or_none()

        return f"{(first_name.name + ' ') if first_name is not None else ''}{last_name.name if last_name is not None else ''}"

    # TODO: Add random desired mutations

    async with session_scope() as session:
        vendor = Vendor(server_discord_id=server_discord_id, name=name or await _get_random_vendor_name())
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
