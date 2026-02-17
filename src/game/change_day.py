import random
from typing import Optional

from database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    add_pooch_to_vendor_stock,
    age_pooch,
    bury_pooch,
    clear_vendor_pooch_stock,
    create_pooch,
    create_vendor,
    decrement_pooch_breeding_cooldown,
    delete_pregnancy,
    get_pooch_health,
    get_pooch_kennel,
    list_living_pooches,
    list_pooch_pregnancies,
    list_servers,
    list_servers_for_pooch,
    list_vendors,
    remove_pooch_from_kennel,
    set_pooch_dead,
)
from game.constants import (
    DEATH_CHANCE_PER_HEALTH_UNDER_MIN,
    MIN_HEALTH_FOR_DEATH_CHANCE,
    NUM_BREEDS_PER_VENDOR_POOCH_RANGE,
    NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE,
    NUM_VENDORS_PER_SERVER,
    POOCH_BASE_HEALTH_RANGE,
    VENDOR_MARKUP_RANGE,
    VENDOR_POOCH_AGE_RANGE,
    VENDOR_POOCH_STOCK_COUNT_RANGE,
)
from game.manage_kennels import add_pooch_to_kennel
from game.manage_pooches import get_pooch_by_id
from logger import get_logger

from .model import BirthEvent, DayChangeSummary, DeathEvent, to_pooch, to_server

logger = get_logger("game/change_day")


def _death_roll(total_health: int, rng: random.Random) -> bool:
    """Randomly determine whether a Pooch should die or not, based on its health."""

    if total_health >= MIN_HEALTH_FOR_DEATH_CHANCE:
        return False
    deficit = MIN_HEALTH_FOR_DEATH_CHANCE - max(total_health, 0)
    chance = min(DEATH_CHANCE_PER_HEALTH_UNDER_MIN * deficit, 1.0)
    return rng.random() < chance


async def run_day_change(rng_seed: Optional[int] = None) -> dict[int, DayChangeSummary]:
    """
    Change the day for all servers, completing pregnancies, resolving deaths, and restocking vendors.

    Parameters
    ----------
    rng_seed: int, optional
        The int to seed `random.Random` with for determining random values (like pooch deaths or vendor restocks).

    Returns
    -------
    dict[int, DayChangeSummary]
        A dictionary summarizing the day's events for each server in the form
        `{ server_discord_id : DayChangeSummary }`.
    """

    rng = random.Random(rng_seed)

    births_by_server: dict[int, list[BirthEvent]] = {}
    deaths_by_server: dict[int, list[DeathEvent]] = {}

    # births
    logger.info("Handling births for the day...")
    pregnancies = await list_pooch_pregnancies()
    for pregnancy in pregnancies:
        mother_id = pregnancy.mother_id
        fetus_id = pregnancy.fetus_id

        await delete_pregnancy(mother_id, fetus_id)

        mother = await get_pooch_by_id(mother_id)
        baby = await get_pooch_by_id(fetus_id)

        servers = await list_servers_for_pooch(baby.id)

        kennel = await get_pooch_kennel(mother_id)
        if kennel is None:
            for server in servers:
                births_by_server.setdefault(server.discord_id, []).append(
                    BirthEvent(
                        server=(await to_server(server)),
                        mother=(await to_pooch(mother)),
                        child=(await to_pooch(baby)),
                        failure_message="The mother doesn't belong to a kennel. Her baby was abandoned.",
                    )
                )
            continue

        success = await add_pooch_to_kennel(kennel.id, baby.id)
        if not success:
            for server in servers:
                births_by_server.setdefault(server.discord_id, []).append(
                    BirthEvent(
                        server=(await to_server(server)),
                        mother=(await to_pooch(mother)),
                        child=(await to_pooch(baby)),
                        failure_message="There wasn't enough space in the mother's kennel. Her baby was crushed.",
                    )
                )
            continue

        for server in servers:
            births_by_server.setdefault(server.discord_id, []).append(
                BirthEvent(
                    server=(await to_server(server)), mother=(await to_pooch(mother)), child=(await to_pooch(baby))
                )
            )
    logger.info("Completed daily births.")

    # deaths (and other updates)
    logger.info("Handling deaths for the day...")
    pooches = await list_living_pooches()
    for pooch in pooches:
        pooch = await decrement_pooch_breeding_cooldown(pooch.id)
        pooch = await age_pooch(pooch.id)
        total_health: int = await get_pooch_health(pooch.id)
        if _death_roll(total_health, rng):
            pooch = await set_pooch_dead(pooch.id)
            await remove_pooch_from_kennel(pooch.id)
            if pooch.owner_discord_id is not None:
                await bury_pooch(pooch.owner_discord_id, pooch.id)
            for server in await list_servers_for_pooch(pooch.id):
                deaths_by_server.setdefault(server.discord_id, []).append(
                    DeathEvent(server=(await to_server(server)), pooch=(await to_pooch(pooch)))
                )
    logger.info("Completed daily deaths.")

    servers = await list_servers()

    # vendor restock
    logger.info("Restocking vendors for the day...")
    for server in servers:
        vendors = await list_vendors(server.discord_id)
        if len(vendors) < NUM_VENDORS_PER_SERVER:
            for _ in range(NUM_VENDORS_PER_SERVER - len(vendors)):
                vendor = await create_vendor(
                    server.discord_id, price_markup=rng.uniform(VENDOR_MARKUP_RANGE[0], VENDOR_MARKUP_RANGE[1]), rng=rng
                )
                vendors.append(vendor)
        for vendor in vendors:
            await clear_vendor_pooch_stock(vendor.id)
            stock_count = rng.randint(VENDOR_POOCH_STOCK_COUNT_RANGE[0], VENDOR_POOCH_STOCK_COUNT_RANGE[1])
            for _ in range(stock_count):
                vendor_pooch = await create_pooch(
                    vendor_id=vendor.id,
                    age=rng.randint(VENDOR_POOCH_AGE_RANGE[0], VENDOR_POOCH_AGE_RANGE[1]),
                    base_health=rng.randint(POOCH_BASE_HEALTH_RANGE[0], POOCH_BASE_HEALTH_RANGE[1]),
                    rng=rng,
                )
                num_breeds = rng.randint(NUM_BREEDS_PER_VENDOR_POOCH_RANGE[0], NUM_BREEDS_PER_VENDOR_POOCH_RANGE[1])
                for _ in range(num_breeds):
                    await add_breed_to_pooch(vendor_pooch.id, weight=(1 / num_breeds))
                for _ in range(
                    rng.randint(NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE[0], NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE[1])
                ):
                    await add_mutation_to_pooch(vendor_pooch.id)
                await add_pooch_to_vendor_stock(vendor.id, vendor_pooch.id)
    logger.info("Completed daily vendor restock.")

    # summaries
    out: dict[int, DayChangeSummary] = {}
    for server in servers:
        out[server.discord_id] = DayChangeSummary(
            server=(await to_server(server)),
            births=births_by_server.get(server.discord_id, []),
            deaths=deaths_by_server.get(server.discord_id, []),
        )
    return out
