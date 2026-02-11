from typing import Optional
from sqlalchemy import select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)


async def age_pooch(pooch_id: int) -> Optional[Pooch]:
    """
    Age the pooch with the given ID by 1, and increase its age health loss if it's old enough.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to age.

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
        if pooch.age > 5:  # TODO
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
        The Pooch ORM object whose breeding cooldown just decreased.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.breeding_cooldown = max(pooch.breeding_cooldown - 1, 0)

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
        The Pooch ORM object that was just killed.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        pooch = (await session.execute(query)).scalar_one_or_none()

        if pooch is None:
            return None

        pooch.alive = False

    return pooch


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
        The Server object the event channel Discord ID was set for, or None if no server with the given Discord ID was found.
    """

    async with session_scope() as session:
        server = await session.get(Server, {"discord_id": server_discord_id})
        if server is not None:
            server.event_channel_discord_id = channel_discord_id

    return server
