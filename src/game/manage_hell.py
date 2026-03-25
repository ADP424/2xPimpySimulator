from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_mutation_to_pooch,
    add_pooch_to_kennel,
    create_pooch,
    damn_pooch,
    delete_pooch,
    get_current_season,
    get_mutation_by_name,
    get_owner_by_discord_id,
    get_pooch_by_id,
    get_pooch_health,
    get_random_breed_ids,
    give_bloodskulls_to_owner,
    give_bones_to_owner,
)
from src.database import list_hell_pooches as db_list_hell_pooches
from src.database import (
    list_kennels_for_owner,
    list_pooch_breeds,
    list_pooch_mutations,
    list_pooches_for_kennel,
    remove_pooch_from_kennel,
    set_pooch_dead,
)

from .constants import (
    BASE_POOCH_BLOODSKULL_VALUE,
    BASE_POOCH_SUMMON_PRICE,
    BLOODSKULL_PRICE_PER_POOCH_SUMMON_ROLL,
    BREED_RARITY_TO_POOCH_VALUE_MULT,
    NUM_BREEDS_PER_SUMMON_POOCH_RANGE,
    POOCH_BLOODSKULL_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE,
    POOCH_STAT_RANGE,
    POOCH_STATS,
)
from .exceptions import PoochNotFound
from .models import to_pooch

if TYPE_CHECKING:
    from .models import Pooch


async def get_pooch_bloodskull_value(pooch_id: int) -> int:
    """
    Get the total bloodskull value the pooch with the given ID has.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the value of.

    Returns
    -------
    int
        The value of the pooch in bloodskulls.
    """

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        raise PoochNotFound(pooch_id)

    # Health loss reduces a pooch's value (or increases if its health is higher than average)
    pooch_health: int = await get_pooch_health(pooch.id)
    average_base_health = (POOCH_STAT_RANGE[1] - POOCH_STAT_RANGE[0]) / 2
    value = BASE_POOCH_BLOODSKULL_VALUE - (
        POOCH_BLOODSKULL_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE * (average_base_health - pooch_health)
    )

    # Mutations have advanced options that affect a pooch's value
    pooch_mutations = await list_pooch_mutations(pooch.id)
    mutation_value_add = 0
    mutation_value_mult = 1
    for mutation in pooch_mutations:
        mutation_value_add += mutation.parameters.get("bloodskull_value_add", 0.0)
        mutation_value_mult *= mutation.parameters.get("bloodskull_value_mult", 1.0)
    value = max(value + mutation_value_add, 0)
    value *= mutation_value_mult

    # Breeds multiply the pooch's value based on their rarity
    pooch_breeds = await list_pooch_breeds(pooch.id)
    breed_value_mult = 0
    for breed, weight in pooch_breeds:
        breed_value_mult += weight * BREED_RARITY_TO_POOCH_VALUE_MULT[breed.rarity]
    value *= breed_value_mult

    return max(round(value), 0)


def get_conjure_pooch_price(num_rolls: int) -> int:
    """
    Return the bloodskull price to conjure a pooch with `num_rolls` rolls.

    Parameters
    ----------
    num_rolls: int
        The number of rolls being made during the pooch conjuring. Minimum of 1.

    Returns
    -------
    int
        The number of bloodskulls the conjure will cost.
    """

    return BASE_POOCH_SUMMON_PRICE + BLOODSKULL_PRICE_PER_POOCH_SUMMON_ROLL * max(num_rolls, 1)


# Backwards-compat alias used by web UI routes (do not remove)
get_summon_pooch_price = get_conjure_pooch_price


async def list_hell_pooches() -> list[Pooch]:
    """
    List every pooch in the global Hell, most recently damned first.

    Returns
    -------
    list[Pooch]
        A list of Pooch objects representing those sacrificed to Hell.
    """

    rows = await db_list_hell_pooches()
    return [await to_pooch(pooch) for pooch in rows]


async def sacrifice_pooch(owner_discord_id: int, pooch_id: int) -> tuple[bool, str]:
    """
    Have the given owner sacrifice the given pooch to Hell for bloodskulls.
    Fails with a specific error message if:
    - The owner doesn't exist.
    - The pooch doesn't exist.
    - The owner doesn't own the pooch.
    - The pooch is already dead.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner making the sacrifice.

    pooch_id: int
        The ID of the pooch being sacrificed.

    Returns
    -------
    tuple[bool, str]
        A tuple in the form `(success?, message)`.
    """

    value = await get_pooch_bloodskull_value(pooch_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return (False, "You need to visit /home first to set up your account.")

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return (False, "That pooch doesn't exist.")
    if pooch.owner_discord_id != owner.discord_id:
        return (False, "You don't own that pooch.")
    if not pooch.alive:
        return (False, "That pooch is already dead.")

    await give_bloodskulls_to_owner(owner_discord_id, value)
    await give_bones_to_owner(owner_discord_id, 1)
    await set_pooch_dead(pooch.id)
    await remove_pooch_from_kennel(pooch.id)
    await damn_pooch(pooch_id)

    return (True, f"You sacrificed {pooch.name} for {value} bloodskulls... 𖤐")


async def conjure_pooch(owner_discord_id: int, num_rolls: int = 1, rng_seed: Optional[int] = None) -> tuple[bool, str]:
    """
    Have the given owner conjure a pooch for bloodskulls.
    Fails with a specific error message if:
    - `num_rolls` is less than 1.
    - The owner doesn't exist.
    - The owner can't afford the conjure price.
    - The owner doesn't have space in any of their kennels.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner conjuring the pooch.

    num_rolls: int, default : 1
        The number of rolls to make for the conjured pooch (the highest value one is kept). Minimum of 1.

    rng_seed: int, optional
        The int to seed `random.Random` with for determining random values (like the pooch's breeds and stats).

    Returns
    -------
    tuple[bool, str]
        A tuple in the form `(success?, message)`.
    """

    rng = random.Random(rng_seed)

    if num_rolls < 1:
        return (False, "You need to make at least 1 roll.")

    price = get_conjure_pooch_price(num_rolls)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return (False, "You need to visit /home first to set up your account.")
    if owner.bloodskulls < price:
        return (False, f"That conjure costs {price} bloodskulls but only have {owner.bloodskulls}.")

    kennels = await list_kennels_for_owner(owner_discord_id)
    target_kennel = None
    for kennel in kennels:
        kennel_pooches = await list_pooches_for_kennel(kennel.id)
        if len(kennel_pooches) < kennel.pooch_limit:
            target_kennel = kennel
            break

    if target_kennel is None:
        return (False, "You don't have any kennel space available.")

    _hell_season = await get_current_season()

    conjured_pooch = None
    for _ in range(num_rolls):
        num_breeds = rng.randint(NUM_BREEDS_PER_SUMMON_POOCH_RANGE[0], NUM_BREEDS_PER_SUMMON_POOCH_RANGE[1])
        ritual_breed_ids = await get_random_breed_ids(num_breeds, rng=rng, from_ritual=True, season=_hell_season)
        pooch = await create_pooch(
            owner_discord_id=owner.discord_id,
            age=0,
            base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
            **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
            breeds=ritual_breed_ids,
            rng=rng,
        )

        if conjured_pooch is None or (
            await get_pooch_bloodskull_value(pooch.id) > await get_pooch_bloodskull_value(conjured_pooch.id)
        ):
            if conjured_pooch is not None:
                await delete_pooch(conjured_pooch.id)
            conjured_pooch = pooch
        else:
            await delete_pooch(pooch.id)

    await give_bloodskulls_to_owner(owner_discord_id, -price)
    await add_pooch_to_kennel(target_kennel.id, conjured_pooch.id)

    mark = await get_mutation_by_name("Mark of the Beast")
    if mark is not None:
        await add_mutation_to_pooch(conjured_pooch.id, mutation_id=mark.id)

    return (
        True,
        (
            f"You conjured {conjured_pooch.name} "
            f"({await get_pooch_bloodskull_value(conjured_pooch.id)} bloodskull value) "
            f"for {price} bloodskulls... 𖤐"
        ),
    )


# Backwards-compat alias used by web UI routes (do not remove)
summon_pooch = conjure_pooch
