from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update

from .constants import POOCH_HEALTH_LOSS_STARTING_AGE
from .models import (
    EventOccurrence,
    Kennel,
    Owner,
    Pooch,
    Server,
    ServerEventOccurrence,
    ServerEventParticipation,
)
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


async def update_owner_discord_name(owner_discord_id: int, discord_name: str) -> Optional[Owner]:
    """
    Update the cached Discord display name for the given owner.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to update.

    discord_name: str
        The new Discord display name.

    Returns
    -------
    Owner, optional
        The updated Owner ORM object, or None if the owner wasn't found.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.discord_name = discord_name

    return owner


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


async def give_bones_to_owner(owner_discord_id: int, bones: int) -> Optional[Owner]:
    """
    Add a number to the given owner's `bones`.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to give the bones to.

    bones: int
        The number of bones to give to the owner (negative to spend).

    Returns
    -------
    Owner, optional
        The Owner ORM object the bones were added to, or None if no owner with the given Discord ID was found.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.bones += bones

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


async def modify_kennel_pooch_limit(kennel_id: int, amount: int) -> Optional[Kennel]:
    """
    Modify a kennel's pooch limit by a given amount.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to modify.

    amount: int
        The amount to add to pooch limit (can be negative) to a minimum of 1.

    Returns
    -------
    Kennel, optional
        The updated Kennel, or None if not found.
    """

    async with session_scope() as session:
        query = select(Kennel).where(Kennel.id == kennel_id)
        result = await session.execute(query)
        kennel = result.scalar_one_or_none()

        if kennel is None:
            return None

        new_limit = max(1, kennel.pooch_limit + amount)
        kennel.pooch_limit = new_limit

        await session.flush()
        return kennel


async def modify_pooch_age(
    pooch_id: int,
    amount: int,
    health_loss_starting_age: int = POOCH_HEALTH_LOSS_STARTING_AGE,
) -> Optional[Pooch]:
    """
    Modify a pooch's age by a given amount.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to modify.

    amount: int
        The amount to add to age (can be negative) to a minimum of 0.

    health_loss_starting_age: int
        The age at which a pooch starts losing health from age.

    Returns
    -------
    Pooch, optional
        The updated Pooch, or None if not found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        result = await session.execute(query)
        pooch = result.scalar_one_or_none()

        if pooch is None:
            return None

        pooch.age = max(0, pooch.age + amount)
        pooch.health_loss_age = max(0, pooch.age - health_loss_starting_age)

        await session.flush()
        return pooch


async def modify_pooch_base_health(pooch_id: int, amount: int) -> Optional[Pooch]:
    """
    Modify a pooch's base health by a given amount.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to modify.

    amount: int
        The amount to add to base health (can be negative) to a minimum of 0.

    Returns
    -------
    Pooch, optional
        The updated Pooch, or None if not found.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        result = await session.execute(query)
        pooch = result.scalar_one_or_none()

        if pooch is None:
            return None

        new_health = max(0, pooch.base_health + amount)
        pooch.base_health = new_health

        await session.flush()
        return pooch


async def set_pooch_base_health(pooch_id: int, health: int) -> Optional[Pooch]:
    """Set a pooch's base health to a specific value (minimum 0)."""

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        result = await session.execute(query)
        pooch = result.scalar_one_or_none()

        if pooch is None:
            return None

        pooch.base_health = max(0, health)

        await session.flush()
        return pooch


async def set_pooch_age(pooch_id: int, age: int) -> Optional[Pooch]:
    """Set a pooch's age to a specific value (minimum 0)."""

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        result = await session.execute(query)
        pooch = result.scalar_one_or_none()

        if pooch is None:
            return None

        pooch.age = max(0, age)
        pooch.health_loss_age = max(0, age - POOCH_HEALTH_LOSS_STARTING_AGE)

        await session.flush()
        return pooch


async def set_owner_dollars(owner_discord_id: int, dollars: int) -> Optional[Owner]:
    """Set an owner's dollars to a specific value."""

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.dollars = dollars

    return owner


async def set_owner_bloodskulls(owner_discord_id: int, bloodskulls: int) -> Optional[Owner]:
    """Set an owner's bloodskulls to a specific value."""

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.bloodskulls = bloodskulls

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


async def reset_begged_today() -> int:
    """
    Reset every owner's `begged_today` flag to False.

    Returns
    -------
    int
        The number of owners whose `begged_today` flag was reset.
    """

    async with session_scope() as session:
        query = select(Owner)
        owners = (await session.execute(query)).scalars().all()

        for owner in owners:
            owner.begged_today = False

        return len(owners)


async def respond_to_active_owner_event(
    active_owner_event_id: int,
    option_id: Optional[int],
    result_summary: dict[str, Any] = None,
) -> Optional[EventOccurrence]:
    """
    Record a response to an active event.

    Parameters
    ----------
    active_owner_event_id: int
        The ID of the active event being responded to.

    option_id: int, optional
        The ID of the option selected (None if no option selected).

    result_summary: dict, optional
        Summary of what happened as a result.

    Returns
    -------
    EventOccurrence, optional
        The updated EventOccurrence, or None if not found.
    """

    if result_summary is None:
        result_summary = {}

    async with session_scope() as session:
        query = (
            update(EventOccurrence)
            .where(EventOccurrence.id == active_owner_event_id, EventOccurrence.archived.is_(False))
            .values(
                responded_at=datetime.now(timezone.utc),
                selected_option_id=option_id,
                result_summary=result_summary,
            )
            .returning(EventOccurrence)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


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


async def set_kennel_pooch_limit(kennel_id: int, limit: int) -> Optional[Kennel]:
    """
    Set a kennel's pooch limit to a specific value.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to modify.

    limit: int
        The new pooch limit (minimum 1).

    Returns
    -------
    Kennel, optional
        The updated Kennel, or None if not found.
    """

    async with session_scope() as session:
        query = select(Kennel).where(Kennel.id == kennel_id)
        result = await session.execute(query)
        kennel = result.scalar_one_or_none()

        if kennel is None:
            return None

        kennel.pooch_limit = max(1, limit)

        await session.flush()
        return kennel


async def reset_visited_park_today() -> int:
    """Reset every owner's `visited_park_today` flag to False."""
    async with session_scope() as session:
        query = select(Owner)
        owners = (await session.execute(query)).scalars().all()
        for owner in owners:
            owner.visited_park_today = False
        return len(owners)


async def set_owner_visited_park_today(owner_discord_id: int, visited: bool = True) -> Optional[Owner]:
    """Set the `visited_park_today` flag for the owner with the given Discord ID."""
    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()
        if owner is None:
            return None
        owner.visited_park_today = visited
    return owner


async def set_owner_begged_today(owner_discord_id: int, begged_today: bool = True) -> Optional[Owner]:
    """
    Set the `begged_today` flag for the owner with the given Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to update.

    begged_today: bool, default : True
        The value to set `begged_today` to.

    Returns
    -------
    Owner, optional
        The Owner ORM object that was updated, or None if no owner with the given Discord ID was found.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        owner = (await session.execute(query)).scalar_one_or_none()

        if owner is None:
            return None

        owner.begged_today = begged_today

    return owner


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


async def update_active_event_result(
    active_owner_event_id: int, result_summary: dict[str, Any]
) -> Optional[EventOccurrence]:
    """
    Update the result summary of an active event.

    Parameters
    ----------
    active_owner_event_id: int
        The ID of the active event to update.

    result_summary: dict[str, Any]
        The result summary to set.

    Returns
    -------
    EventOccurrence, optional
        The updated EventOccurrence, or None if not found.
    """

    async with session_scope() as session:
        query = (
            update(EventOccurrence)
            .where(EventOccurrence.id == active_owner_event_id, EventOccurrence.archived.is_(False))
            .values(result_summary=result_summary)
            .returning(EventOccurrence)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def update_active_event_context(active_owner_event_id: int, context: dict[str, Any]) -> Optional[EventOccurrence]:
    """
    Update the context of an active event.

    Used to persist named slots written by trigger-time actions so they are
    available when the player responds or the event expires.

    Parameters
    ----------
    active_owner_event_id: int
        The ID of the active event to update.

    context: dict[str, Any]
        The updated context to store.

    Returns
    -------
    EventOccurrence, optional
        The updated EventOccurrence, or None if not found.
    """

    async with session_scope() as session:
        query = (
            update(EventOccurrence)
            .where(EventOccurrence.id == active_owner_event_id, EventOccurrence.archived.is_(False))
            .values(context=context)
            .returning(EventOccurrence)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def set_server_event_occurrence_message_discord_id(
    occurrence_id: int, message_discord_id: int | None
) -> Optional[ServerEventOccurrence]:
    async with session_scope() as session:
        query = select(ServerEventOccurrence).where(ServerEventOccurrence.id == occurrence_id)
        occurrence = (await session.execute(query)).scalar_one_or_none()
        if occurrence is None:
            return None
        occurrence.message_discord_id = message_discord_id
        await session.flush()
        return occurrence


async def resolve_server_event_occurrence(
    occurrence_id: int, result_summary: dict[str, Any] | None = None
) -> Optional[ServerEventOccurrence]:
    async with session_scope() as session:
        query = select(ServerEventOccurrence).where(ServerEventOccurrence.id == occurrence_id)
        occurrence = (await session.execute(query)).scalar_one_or_none()
        if occurrence is None:
            return None
        occurrence.result_summary = result_summary or {}
        occurrence.resolved_at = datetime.now(timezone.utc)
        occurrence.archived = True
        await session.flush()
        return occurrence


async def finalize_server_event_participation(
    participation_id: int,
    resolution_result: dict[str, Any] | None = None,
    score: float | None = None,
    rank: int | None = None,
) -> Optional[ServerEventParticipation]:
    async with session_scope() as session:
        query = select(ServerEventParticipation).where(ServerEventParticipation.id == participation_id)
        participation = (await session.execute(query)).scalar_one_or_none()
        if participation is None:
            return None
        participation.resolution_result = resolution_result or {}
        participation.score = score
        participation.rank = rank
        await session.flush()
        return participation
