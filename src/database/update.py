from typing import Optional

from sqlalchemy import select

from .constants import POOCH_HEALTH_LOSS_STARTING_AGE
from .models import Kennel, Owner, Pooch, Server
from .session import session_scope


async def age_pooch(pooch_id: int, health_loss_starting_age: int = POOCH_HEALTH_LOSS_STARTING_AGE) -> Optional[Pooch]:
    """
    Age the pooch with the given ID by 1, and increase its age health loss if it's old enough.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to age.

    health_loss_starting_age: int
        The minimum age a pooch needs to be to start losing health with age.
        If this function ages the pooch beyond this number, it adds 1 to `health_loss_age`.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object that just aged, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.age += 1
        if pooch.age > health_loss_starting_age:
            pooch.health_loss_age += 1

    return pooch


async def decrement_pooch_breeding_cooldown(pooch_id: int) -> Optional[Pooch]:
    """
    Decrease the breeding cooldown of the pooch with the given ID by 1, to a minimum of 0.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to decrease the breeding cooldown of.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object whose breeding cooldown just decreased, or None if no pooch was found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.breeding_cooldown = max(pooch.breeding_cooldown - 1, 0)

    return pooch


async def give_bloodskulls_to_owner(owner_discord_id: int, bloodskulls: int) -> Optional[Owner]:
    """
    Add a number to the given owner's `bloodskulls`.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to give the bloodskulls to.

    bloodskulls: int
        The number of bloodskulls to give to the owner.

    Returns
    -------
    Owner, optional
        The Owner ORM object the bloodskulls were added to, or None if no owner with the given Discord ID was found.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.bloodskulls += bloodskulls

    return owner


async def give_money_to_owner(owner_discord_id: int, dollars: int) -> Optional[Owner]:
    """
    Add an amount of money to the given owner's `dollars`.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to give the money to.

    dollars: int
        The number of dollars to give to the owner.

    Returns
    -------
    Owner, optional
        The Owner ORM object the dollars were added to, or None if no owner with the given Discord ID was found.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.dollars += dollars

    return owner


async def rename_kennel(kennel_id: int, name: str) -> Optional[Kennel]:
    """
    Replace the name of the kennel with the given ID with a new one.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to rename.

    name: str
        The new name to give the kennel.

    Returns
    -------
    Kennel, optional
        The Kennel ORM object that was renamed, or None if the kennel wasn't found.
    """

    async with session_scope() as session:
        query = select(Kennel).where(Kennel.id == kennel_id)
        kennel = (await session.execute(query)).scalar_one_or_none()

        if kennel is None:
            return None

        kennel.name = name

    return kennel


async def rename_pooch(pooch_id: int, name: str) -> Optional[Pooch]:
    """
    Replace the name of the pooch with the given ID with a new one.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to rename.

    name: str
        The new name to give the pooch.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object that was renamed, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.name = name

    return pooch


async def set_event_channel_discord_id(server_discord_id: int, channel_discord_id: int) -> Optional[Server]:
    """
    Set the channel for automated events to be sent to for the server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The ID of the server to set the event channel of.

    channel_discord_id: int
        The Discord ID of the channel to send automated events for the server to.

    Returns
    -------
    Server, optional
        The Server object the event channel Discord ID was set for, or None if no server with
        the given Discord ID was found.
    """

    async with session_scope() as session:
        server = await session.get(Server, {"discord_id": server_discord_id})
        if server is not None:
            server.event_channel_discord_id = channel_discord_id

    return server


async def set_pooch_breeding_cooldown(pooch_id: int, cooldown: int) -> Optional[Pooch]:
    """
    Set the breeding cooldown of a pooch, to a minimum of 0.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to set the cooldown of.

    cooldown: int
        The value to set the pooch's breeding cooldown to.

    Returns
    -------
    Pooch, optional
        The Pooch whose cooldown was set, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()
        if pooch is None:
            return None
        pooch.breeding_cooldown = max(cooldown, 0)

    return pooch


async def set_pooch_dead(pooch_id: int) -> Optional[Pooch]:
    """
    Set the pooch with the given ID to dead.
    Doesn't move the pooch to a graveyard. Call `bury_pooch` to do that.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to kill.

    Returns
    -------
    Pooch, optional
        The Pooch ORM object that was just killed, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.alive = False

    return pooch


async def set_pooch_virgin(pooch_id: int, virgin: bool = True) -> Optional[Pooch]:
    """
    Set the virgin flag of a pooch, True by default.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to update the virginity status of.

    virgin: bool, default : True
        `True` to set the pooch to a virgin, `False` to lose their virginity.

    Returns
    -------
    Pooch, optional
        The Pooch object whose virginity status was changed, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()
        if pooch is None:
            return None
        pooch.virgin = virgin

    return pooch


async def transfer_pooch_to_owner(pooch_id: int, owner_discord_id: int) -> Optional[Pooch]:
    """
    Transfer a pooch to a new owner, clearing any vendor association.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to transfer.

    owner_discord_id: int
        The Discord ID of the new owner.

    Returns
    -------
    Pooch, optional
        The updated Pooch ORM object, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.owner_discord_id = owner_discord_id
        pooch.vendor_id = None

    return pooch


async def transfer_pooch_to_vendor(pooch_id: int, vendor_id: int) -> Optional[Pooch]:
    """
    Transfer a pooch to a new vendor, clearing any owner association.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to transfer.

    vendor_id: int
        The ID of the vendor to own the pooch.

    Returns
    -------
    Pooch, optional
        The updated Pooch ORM object, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.vendor_id = vendor_id
        pooch.owner_discord_id = None

    return pooch
