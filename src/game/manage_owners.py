from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_owner_to_server,
    add_pooch_to_kennel,
    add_pooch_to_strays,
    count_owners_for_server,
    create_kennel,
    create_owner,
    create_pooch,
    get_owner_by_discord_id,
    get_owner_server,
    get_random_breed_ids,
    give_bones_to_owner,
    give_money_to_owner,
    list_kennels_for_owner,
    list_owners,
    list_pooches_for_kennel,
    list_strays_for_server,
    remove_pooch_from_strays,
    set_owner_begged_today,
    set_owner_visited_park_today,
    transfer_pooch_to_owner,
    update_owner_discord_name,
)
from src.logger import get_logger

from .constants import (
    BEG_DOLLARS_RANGE,
    BEG_MAX_DOLLARS,
    PARK_STRAY_CATCH_DIVISOR,
    POOCH_STAT_RANGE,
    POOCH_STATS,
)
from .exceptions import OwnerNotFound
from .manage_auctions import cancel_listing_for_pooch
from .manage_servers import get_or_create_server
from .models import to_kennel, to_owner

if TYPE_CHECKING:
    from .models import Kennel, Owner

logger = get_logger("game/manage_owners")


async def add_money(server_discord_id: int, owner_discord_id: int, amount: int) -> Owner:
    """
    Add money to the owner with the given ID's account.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server the owner is getting the money on.

    owner_discord_id: int
        The Discord ID of the owner to give the money.

    Returns
    -------
    Owner
        The Owner with the given Discord ID that received the money.
    """

    owner = await give_money_to_owner(owner_discord_id, amount)
    if owner is None:
        await get_or_create_owner(server_discord_id, owner_discord_id)
        owner = await give_money_to_owner(owner_discord_id, amount)
        if owner is None:
            raise OwnerNotFound(owner_discord_id)
    return await to_owner(owner)


async def beg_for_money(
    server_discord_id: int, owner_discord_id: int, rng: random.Random | None = None
) -> tuple[int, Optional[str]]:
    """
    Beg for money at the church.

    An owner may only beg once per day, and only if they have `BEG_MAX_DOLLARS` or fewer dollars.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server the owner is begging in.

    owner_discord_id: int
        The Discord ID of the owner begging.

    rng: Random, optional
        The random generator to use to determine the amount.

    Returns
    -------
    tuple[int, str, optional]
        The a tuple in the form (amount of money received, failure message or None if success).
    """

    rng = rng if rng is not None else random.Random()

    await get_or_create_owner(server_discord_id, owner_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        raise OwnerNotFound(owner_discord_id)

    if owner.dollars > BEG_MAX_DOLLARS:
        return 0, "You have too much money to beg. Shame!"
    if owner.begged_today:
        return 0, "You already begged today, friend."

    amount = rng.randint(BEG_DOLLARS_RANGE[0], BEG_DOLLARS_RANGE[1])
    await give_money_to_owner(owner_discord_id, amount)
    await set_owner_begged_today(owner_discord_id)

    return amount, None


async def get_or_create_owner(
    server_discord_id: int,
    owner_discord_id: int,
    rng: Optional[random.Random] = None,
) -> Owner:
    """
    Get an owner with the given Discord ID for the server with the given Discord ID.
    If no owner with that ID exists on that server yet, create it.
    Also creates the server if it doesn't exist yet.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to get the owner from / add the owner to.

    owner_discord_id: int
        The Discord ID of the owner to get / create / add to the server.

    rng: Random, optional
        The random generator to use when creating starting pooches. A fresh one is created if not given.

    Returns
    -------
    Owner
        The Owner with the given Discord ID in the server with the given Discord ID.
    """

    rng = rng if rng is not None else random.Random()

    async def _create_owner_starting_objects(owner_discord_id: int):
        """Add the owner to the server and give them their starting items."""

        await add_owner_to_server(server_discord_id, owner_discord_id)
        kennel = await create_kennel(owner_discord_id)
        female_breed_ids = await get_random_breed_ids(1, rng=rng, from_vendor=True)
        male_breed_ids = await get_random_breed_ids(1, rng=rng, from_vendor=True)
        female_pooch = await create_pooch(
            owner_discord_id=owner_discord_id,
            sex="female",
            age=1,
            breeding_cooldown=0,
            base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
            **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
            breeds=female_breed_ids,
            rng=rng,
        )
        male_pooch = await create_pooch(
            owner_discord_id=owner_discord_id,
            sex="male",
            age=1,
            breeding_cooldown=0,
            base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
            **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
            breeds=male_breed_ids,
            rng=rng,
        )
        await add_pooch_to_kennel(kennel.id, female_pooch.id)
        await add_pooch_to_kennel(kennel.id, male_pooch.id)

    await get_or_create_server(server_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        owner = await create_owner(owner_discord_id)
        await _create_owner_starting_objects(owner.discord_id)
    else:
        owner_server = await get_owner_server(server_discord_id, owner_discord_id)
        if owner_server is None:
            await add_owner_to_server(server_discord_id, owner_discord_id)

    return await to_owner(owner)


async def list_owner_kennels(owner_discord_id: int) -> list[Kennel]:
    """
    Get a list of every kennel the owner with the given Discord ID owns.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to get the kennels for.

    Returns
    -------
    list[Kennel]
        The list of kennels the owner with the given Discord ID owns.
    """

    kennels = await list_kennels_for_owner(owner_discord_id)
    return [(await to_kennel(kennel)) for kennel in kennels]


async def list_all_owners() -> list[Owner]:
    """
    List all owners in the database.

    Returns
    -------
    list[Owner]
        A list of every Owner as a game dataclass.
    """

    owners = await list_owners()
    return [await to_owner(owner) for owner in owners]


async def update_owner_names(names: dict[int, str]) -> int:
    """
    Update cached Discord display names for owners.

    Parameters
    ----------
    names: dict[int, str]
        Mapping of owner Discord IDs to their current display names.

    Returns
    -------
    int
        The number of owners whose names were actually changed.
    """

    owners = await list_owners()
    owners_by_id = {o.discord_id: o for o in owners}

    updated = 0
    for discord_id, name in names.items():
        owner = owners_by_id.get(discord_id)
        if owner is None or owner.discord_name == name:
            continue
        await update_owner_discord_name(discord_id, name)
        updated += 1

    logger.info(f"Updated {updated}/{len(owners)} owner display names")
    return updated


async def _attempt_catch_stray(
    server_discord_id: int,
    owner_discord_id: int,
    rng: random.Random,
) -> tuple[bool, str]:
    """Roll one attempt to attract a stray. Does NOT check or set any daily flags."""
    strays = await list_strays_for_server(server_discord_id)
    if not strays:
        return False, "You sit in the park for a while, but no stray pooches appear."

    owner_count = await count_owners_for_server(server_discord_id)
    catch_chance = min(len(strays) / max(owner_count, 1) / PARK_STRAY_CATCH_DIVISOR, 1.0)

    if rng.random() > catch_chance:
        return False, "You sit in the park for a while, but no stray pooches come close enough to catch."

    chosen = rng.choice(strays)
    await remove_pooch_from_strays(chosen.id)
    await cancel_listing_for_pooch(chosen.id)
    await transfer_pooch_to_owner(chosen.id, owner_discord_id)

    kennels = await list_kennels_for_owner(owner_discord_id)
    for kennel in kennels:
        pooches_in_kennel = await list_pooches_for_kennel(kennel.id)
        if len(pooches_in_kennel) < kennel.pooch_limit:
            await add_pooch_to_kennel(kennel.id, chosen.id)
            return (
                True,
                f"A stray pooch named **{chosen.name}** trotted up to you! They've been placed in **{kennel.name}**.",
            )

    return (
        True,
        (
            f"A stray pooch named **{chosen.name}** trotted up to you! "
            "They're waiting in town until you make room in a kennel."
        ),
    )


async def visit_park(
    server_discord_id: int, owner_discord_id: int, rng: random.Random | None = None
) -> tuple[bool, str]:
    """
    Attempt to attract a stray pooch at the park.

    Catch chance = min(stray_count / owner_count / PARK_STRAY_CATCH_DIVISOR, 1.0).
    An owner may only visit the park once per day.
    On success the stray is delivered to the first kennel with free space, or left in town if none.

    Returns
    -------
    tuple[bool, str]
        (caught, message) — caught is True if a stray was attracted, False otherwise.
    """

    rng = rng if rng is not None else random.Random()

    await get_or_create_owner(server_discord_id, owner_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        raise OwnerNotFound(owner_discord_id)

    if owner.visited_park_today:
        return False, "You already spent time at the park today. Come back tomorrow."

    await set_owner_visited_park_today(owner_discord_id)

    return await _attempt_catch_stray(server_discord_id, owner_discord_id, rng)


async def spend_bone_at_park(
    server_discord_id: int, owner_discord_id: int, rng: random.Random | None = None
) -> tuple[bool, str]:
    """
    Spend one bone to get an additional stray-attraction attempt at the park.

    Bones are earned by sacrificing pooches. Unlike the free daily visit, bone
    attempts are not limited — each bone buys exactly one roll.

    Returns
    -------
    tuple[bool, str]
        (caught, message) — caught is True if a stray was attracted, False otherwise.
        Returns (False, error_message) if the owner has no bones.
    """

    rng = rng if rng is not None else random.Random()

    await get_or_create_owner(server_discord_id, owner_discord_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        raise OwnerNotFound(owner_discord_id)

    if owner.bones < 1:
        return False, "You don't have any bones to spend."

    await give_bones_to_owner(owner_discord_id, -1)

    return await _attempt_catch_stray(server_discord_id, owner_discord_id, rng)


async def cast_out_pooch(pooch_id: int, server_discord_id: int) -> None:
    await cancel_listing_for_pooch(pooch_id)
    await add_pooch_to_strays(pooch_id, server_discord_id)
