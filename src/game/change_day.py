import random
from typing import Optional

from game.manage_pooches import get_pooch_by_id
from game.manage_kennels import add_pooch_to_kennel

from .model import BirthEvent, DeathEvent, DayChangeSummary, to_pooch, to_server

from database import (
    list_living_pooches,
    list_pooch_pregnancies,
    delete_pregnancy,
    get_pooch_kennel,
    create_pooch,
    decrement_pooch_breeding_cooldown,
    age_pooch,
    remove_pooch_from_kennel,
    set_pooch_dead,
    bury_pooch,
    list_vendors,
    clear_vendor_pooch_stock,
    add_pooch_to_vendor_stock,
    create_vendor,
    list_servers_for_pooch,
    list_servers,
)


def _death_roll(total_health: int, rng: random.Random) -> bool:
    """Randomly determine whether a Pooch should die or not, based on its health."""

    if total_health >= 5:  # TODO
        return False
    deficit = 5 - max(total_health, 0)
    chance = min(0.2 * deficit, 1.0)
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
        A dictionary summarizing the day's events for each server in the form `{ server_discord_id : DayChangeSummary }`.
    """

    rng = random.Random(rng_seed)

    births_by_server: dict[int, list[BirthEvent]] = {}
    deaths_by_server: dict[int, list[DeathEvent]] = {}

    # births
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
                        server=to_server(server),
                        mother=to_pooch(mother),
                        child=to_pooch(baby),
                        failure_message="The mother doesn't belong to a kennel. Her baby was abandoned.",
                    )
                )
            continue

        success = await add_pooch_to_kennel(kennel.id, baby.id)
        if not success:
            for server in servers:
                births_by_server.setdefault(server.discord_id, []).append(
                    BirthEvent(
                        server=to_server(server),
                        mother=to_pooch(mother),
                        child=to_pooch(baby),
                        failure_message="There wasn't enough space in the mother's kennel. Her baby was crushed.",
                    )
                )
            continue

        for server in servers:
            births_by_server.setdefault(server.discord_id, []).append(
                BirthEvent(server=to_server(server), mother=to_pooch(mother), child=to_pooch(baby))
            )

    # deaths (and other updates)
    pooches = await list_living_pooches()
    for pooch in pooches:
        await decrement_pooch_breeding_cooldown(pooch.id)
        updated = await age_pooch(pooch.id)
        if updated is None:
            continue

        total_health = max(updated.base_health - updated.health_loss_age, 0)
        if _death_roll(total_health, rng):
            await set_pooch_dead(pooch.id)
            await remove_pooch_from_kennel(pooch.id)
            if pooch.owner_discord_id is not None:
                await bury_pooch(pooch.owner_discord_id, pooch.id)
            for server in await list_servers_for_pooch(baby.id):
                deaths_by_server.setdefault(server.discord_id, []).append(
                    DeathEvent(server=to_server(server), pooch=to_pooch(pooch))
                )

    servers = await list_servers()

    # vendor restock
    for server in servers:
        vendors = await list_vendors(server.discord_id)
        if len(vendors) < 3:
            for _ in range(3 - len(vendors)):  # TODO: Remove this and all magic numbers
                vendor = await create_vendor(server.discord_id, rng_seed=rng_seed)
                vendors.append(vendor)
        for vendor in vendors:
            await clear_vendor_pooch_stock(vendor.id)
            stock_count = rng.randint(2, 5)  # TODO
            for _ in range(stock_count):
                vendor_pooch = await create_pooch(vendor_id=vendor.id, age=rng.randint(0, 5), rng_seed=rng_seed)  # TODO
                await add_pooch_to_vendor_stock(vendor.id, vendor_pooch.id)

    # summaries
    out: dict[int, DayChangeSummary] = {}
    for server in servers:
        out[server.discord_id] = DayChangeSummary(
            server=to_server(server),
            births=births_by_server.get(server.discord_id, []),
            deaths=deaths_by_server.get(server.discord_id, []),
        )
    return out
