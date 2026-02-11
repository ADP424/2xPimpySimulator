import random
from typing import Dict, List, Optional

from .model import BirthEvent, DeathEvent, DayChangeSummary
from .manage_pooches import get_pooch_by_id

from database import (
    list_living_pooches,
    list_pooch_pregnancies,
    delete_pregnancy,
    get_pooch_kennel,
    create_pooch,
    add_pooch_to_kennel,
    decrement_pooch_breeding_cooldown,
    age_pooch,
    remove_pooch_from_kennel,
    set_pooch_dead,
    bury_pooch,
    list_vendors,
    clear_vendor_pooch_stock,
    add_pooch_to_vendor_stock,
    list_servers,
    create_vendor,
)


def _death_roll(total_health: int, rng: random.Random) -> bool:
    if total_health >= 5:
        return False
    deficit = 5 - max(total_health, 0)
    chance = min(0.2 * deficit, 1.0)
    return rng.random() < chance


async def run_day_change(rng_seed: Optional[int] = None) -> Dict[int, DayChangeSummary]:
    rng = random.Random(rng_seed)

    births_by_server: Dict[int, List[BirthEvent]] = {}
    deaths_by_server: Dict[int, List[DeathEvent]] = {}

    all_servers = await list_servers()
    server_ids: set[int] = {int(server.id) for server in all_servers}

    # births
    pregnancies = await list_pooch_pregnancies()
    for pregnancy in pregnancies:
        server_id = int(pregnancy.server_id)
        mother_id = int(pregnancy.mother_id)
        fetus_id = int(pregnancy.fetus_id)

        server_ids.add(server_id)

        await delete_pregnancy(server_id, mother_id, fetus_id)

        mother = await get_pooch_by_id(server_id, mother_id)
        baby = await create_pooch(
            server_id=server_id,
            owner_discord_id=mother.owner_discord_id,
        )

        kennel_id = await get_pooch_kennel(server_id, mother_id)
        if kennel_id is not None:
            await add_pooch_to_kennel(server_id, kennel_id, int(baby.id))

        births_by_server.setdefault(server_id, []).append(
            BirthEvent(server_id=server_id, mother_id=mother_id, child_id=int(baby.id))
        )

    # deaths (and other updates)
    pooches = await list_living_pooches()
    for pooch in pooches:
        server_id = int(pooch.server_id)
        pooch_id = int(pooch.id)

        server_ids.add(server_id)

        await decrement_pooch_breeding_cooldown(server_id, pooch_id)
        updated = await age_pooch(server_id, pooch_id)
        if updated is None:
            continue

        game_pooch = await get_pooch_by_id(server_id, pooch_id)
        if _death_roll(game_pooch.health, rng):
            await set_pooch_dead(server_id, pooch_id)
            await remove_pooch_from_kennel(server_id, pooch_id)
            if game_pooch.owner_discord_id is not None:
                await bury_pooch(server_id, int(game_pooch.owner_discord_id), pooch_id)
            deaths_by_server.setdefault(server_id, []).append(DeathEvent(server_id=server_id, pooch_id=pooch_id))

    # vendor restock (run for every known server, even if no births/deaths)
    for server_id in sorted(server_ids):
        vendors = await list_vendors(server_id)
        if len(vendors) < 3:
            for _ in range(3 - len(vendors)):  # TODO: Remove this and all magic numbers
                vendor = await create_vendor(server_id)
                vendors.append(vendor)
        for vendor in vendors:
            vendor_id = int(vendor.id)
            await clear_vendor_pooch_stock(server_id, vendor_id)
            stock_n = rng.randint(2, 5)
            for _ in range(stock_n):
                vendor_pooch = await create_pooch(server_id=server_id, owner_discord_id=None)
                await add_pooch_to_vendor_stock(server_id, vendor_id, int(vendor_pooch.id))

    # summaries (always emit one per server)
    out: Dict[int, DayChangeSummary] = {}
    for server_id in sorted(server_ids):
        out[server_id] = DayChangeSummary(
            server_id=server_id,
            births=births_by_server.get(server_id, []),
            deaths=deaths_by_server.get(server_id, []),
        )
    return out
