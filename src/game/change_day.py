from __future__ import annotations

import random
from typing import Optional

from src.database import (
    add_mutation_to_pooch,
    add_pooch_to_strays,
    add_pooch_to_vendor_stock,
    clear_vendor_pooch_stock,
    create_pooch,
    create_vendor,
    delete_random_vendor,
    get_current_season,
    get_random_breed_ids,
    increment_global_day,
    list_hell_pooches,
    list_living_pooches,
    list_owners,
    list_servers,
    list_strays_for_server,
    list_vendor_desired_breeds,
    list_vendor_desired_mutations,
    list_vendors,
    reset_begged_today,
    reset_pooch_breeding_cooldown,
    reset_visited_park_today,
    set_owner_hand_cleaned_today,
    update_pooch_mood,
)
from src.logger import get_logger

from .constants import (
    NUM_BREEDS_PER_VENDOR_POOCH_RANGE,
    NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE,
    NUM_VENDORS_PER_SERVER,
    POOCH_BREEDING_COOLDOWN,
    POOCH_HEALTH_LOSS_STARTING_AGE,
    POOCH_STAT_RANGE,
    POOCH_STATS,
    VENDOR_MARKUP_RANGE,
    VENDOR_POOCH_AGE_RANGE,
    VENDOR_POOCH_STOCK_COUNT_RANGE,
)
from .events.stray_events import run_daily_stray_event_check
from .manage_auctions import process_expired_sale_listings
from .manage_stats import get_pooch_health

logger = get_logger("game/change_day")


MOODS = ["happy", "excited", "sleepy", "grumpy", "anxious", "mischievous", "zoomies", "hungry", "content", "clingy"]

# Base weights for each mood (index-matched to MOODS)
_BASE_MOOD_WEIGHTS = [15, 10, 10, 5, 5, 10, 10, 10, 15, 10]


def _pick_mood(total_health: int, age: int, rng: random.Random) -> str:
    """Pick a random mood for a pooch, biased by health and age."""
    weights = list(_BASE_MOOD_WEIGHTS)

    # Low health → more anxious, grumpy
    if total_health <= 3:
        weights[4] += 20  # anxious
        weights[3] += 15  # grumpy
        weights[0] -= 10  # happy
        weights[6] -= 8  # zoomies

    # High health → more happy, excited, zoomies
    elif total_health >= 8:
        weights[0] += 10  # happy
        weights[1] += 10  # excited
        weights[6] += 10  # zoomies

    # Old → more sleepy, grumpy, content
    if age >= POOCH_HEALTH_LOSS_STARTING_AGE:
        weights[2] += 15  # sleepy
        weights[3] += 10  # grumpy
        weights[8] += 10  # content
        weights[6] -= 8  # zoomies
        weights[5] -= 5  # mischievous

    # Young → more zoomies, mischievous, excited
    elif age < 5:
        weights[6] += 15  # zoomies
        weights[5] += 15  # mischievous
        weights[1] += 10  # excited
        weights[2] -= 5  # sleepy

    # Clamp to minimum 1
    weights = [max(w, 1) for w in weights]

    return rng.choices(MOODS, weights=weights, k=1)[0]


async def refresh_moods(rng_seed: Optional[int] = None) -> int:
    """
    Refresh the mood of every living pooch without changing the day.

    Returns
    -------
    int
        The number of pooches whose mood was updated.
    """
    rng = random.Random(rng_seed)
    count = 0

    pooches = await list_living_pooches()
    for pooch in pooches:
        total_health: int = await get_pooch_health(pooch.id)
        new_mood = _pick_mood(total_health, pooch.age, rng)
        await update_pooch_mood(pooch.id, new_mood)
    count += len(pooches)

    # Set "dead" mood on all hell pooches
    hell_pooches = await list_hell_pooches()
    hell_updated = 0
    for pooch in hell_pooches:
        if pooch.mood != "dead":
            await update_pooch_mood(pooch.id, "dead")
            hell_updated += 1
    count += hell_updated

    logger.info("Refreshed moods for %d pooches (%d hell pooches).", count, hell_updated)
    return count


async def run_day_change(
    rng_seed: Optional[int] = None,
) -> dict[int, list[tuple[str, object]]]:
    """
    Run the daily server-level bookkeeping: vendor restock, auction expiry,
    minimum stray guarantee, and stray events.

    Births, deaths, disease ticks, and daily resets are handled by the hourly
    loop (change_hour.py) and are no longer duplicated here.

    Parameters
    ----------
    rng_seed: int, optional
        The int to seed `random.Random` with for determining random values
        (like vendor restocks and stray creation).

    Returns
    -------
    dict[int, list[tuple[str, StrayEventResult]]]
        A mapping of server_discord_id → list of (event_name, result) pairs
        for triggered stray events.
    """

    rng = random.Random(rng_seed)

    servers = await list_servers()
    _season = await get_current_season()

    # increment global day counter
    await increment_global_day()

    # reset daily owner flags
    logger.info("Resetting daily owner flags...")
    await reset_begged_today()
    await reset_visited_park_today()
    for owner in await list_owners():
        await set_owner_hand_cleaned_today(owner.discord_id, False)
    logger.info("Daily owner flags reset.")

    # moods drift once a day with each pooch's health and age
    await refresh_moods(rng_seed=rng_seed)

    # minimum stray guarantee: every server must have at least one alive stray
    logger.info("Checking minimum stray population per server...")
    for server in servers:
        strays = await list_strays_for_server(server.discord_id)
        if not strays:
            stray_breed_ids = await get_random_breed_ids(1, rng=rng, season=_season)
            stray_pooch = await create_pooch(
                base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
                **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
                age=0,
                breeds=stray_breed_ids,
                rng=rng,
            )
            if stray_pooch:
                await add_pooch_to_strays(stray_pooch.id, server.discord_id)
                logger.info(f"Added guaranteed stray pooch {stray_pooch.id} to server {server.discord_id}.")
    logger.info("Minimum stray check complete.")

    # vendor restock (replace one vendor per server, then replace the stock of all vendors)
    logger.info("Restocking vendors for the day...")
    for server in servers:
        await delete_random_vendor(server.discord_id)
        vendors = await list_vendors(server.discord_id)
        for _ in range(NUM_VENDORS_PER_SERVER - len(vendors)):
            vendor = await create_vendor(
                server.discord_id, price_markup=rng.uniform(VENDOR_MARKUP_RANGE[0], VENDOR_MARKUP_RANGE[1]), rng=rng
            )
            vendors.append(vendor)
        # Collect all desired breed/mutation IDs across this server's vendors so
        # stock pooches are never created with breeds or mutations that any vendor desires.
        desired_breed_ids: list[int] = []
        desired_mutation_ids: list[int] = []
        for v in vendors:
            desired_breed_ids.extend(b.id for b in (await list_vendor_desired_breeds(v.id)))
            desired_mutation_ids.extend(m.id for m in (await list_vendor_desired_mutations(v.id)))
        desired_breed_ids = list(set(desired_breed_ids))
        desired_mutation_ids = list(set(desired_mutation_ids))

        for vendor in vendors:
            await clear_vendor_pooch_stock(vendor.id, delete_pooches=True)
            stock_count = rng.randint(VENDOR_POOCH_STOCK_COUNT_RANGE[0], VENDOR_POOCH_STOCK_COUNT_RANGE[1])
            for _ in range(stock_count):
                num_breeds = rng.randint(NUM_BREEDS_PER_VENDOR_POOCH_RANGE[0], NUM_BREEDS_PER_VENDOR_POOCH_RANGE[1])
                vendor_breed_ids = await get_random_breed_ids(
                    num_breeds,
                    rng=rng,
                    from_vendor=True,
                    exclude_ids=desired_breed_ids,
                    season=_season,
                )
                vendor_pooch = await create_pooch(
                    vendor_id=vendor.id,
                    age=rng.randint(VENDOR_POOCH_AGE_RANGE[0], VENDOR_POOCH_AGE_RANGE[1]),
                    base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
                    **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
                    breeds=vendor_breed_ids,
                    rng=rng,
                )
                await reset_pooch_breeding_cooldown(
                    vendor_pooch.id, base_cooldown=POOCH_BREEDING_COOLDOWN, multiplier=0.5
                )
                for _ in range(
                    rng.randint(NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE[0], NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE[1])
                ):
                    await add_mutation_to_pooch(
                        vendor_pooch.id,
                        from_vendor=True,
                        exclude_mutation_ids=desired_mutation_ids,
                        season=_season,
                    )
                await add_pooch_to_vendor_stock(vendor.id, vendor_pooch.id)
    logger.info("Completed daily vendor restock.")

    # auction expiry resolution
    logger.info("Resolving expired auction listings...")
    await process_expired_sale_listings()
    logger.info("Completed auction expiry resolution.")

    # stray events (fire once per server after the stray population is guaranteed)
    logger.info("Running daily stray events...")
    stray_event_results = await run_daily_stray_event_check(rng_seed=rng_seed)
    logger.info("Completed daily stray events.")

    return stray_event_results
