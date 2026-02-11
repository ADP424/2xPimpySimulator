import random
from typing import Optional

from .model import BirthEvent, DeathEvent, DayChangeSummary

from database import (
    list_living_pooches,
    list_pooch_pregnancies,
    delete_pregnancy,
    get_pooch_kennel,
    get_pooch_by_id as db_get_pooch_by_id,
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


async def _build_vendor_server_map(server_ids: set[int]) -> dict[int, int]:
    """Build a mapping from vendor_id to server discord_id."""
    vendor_server: dict[int, int] = {}
    for sid in server_ids:
        vendors = await list_vendors(sid)
        for v in vendors:
            vendor_server[int(v.id)] = sid
    return vendor_server


def _resolve_server_id(
    pooch,
    vendor_server_map: dict[int, int],
    server_ids: set[int],
) -> Optional[int]:
    """Determine which server a pooch ORM object belongs to."""
    if pooch.vendor_id is not None:
        server = vendor_server_map.get(int(pooch.vendor_id))
        if server is not None:
            return server
    # For player-owned pooches, if there is exactly one server, use it
    if len(server_ids) == 1:
        return next(iter(server_ids))
    return None


async def run_day_change(rng_seed: Optional[int] = None) -> dict[int, DayChangeSummary]:
    rng = random.Random(rng_seed)

    births_by_server: dict[int, list[BirthEvent]] = {}
    deaths_by_server: dict[int, list[DeathEvent]] = {}

    all_servers = await list_servers()
    server_ids: set[int] = {int(server.discord_id) for server in all_servers}

    vendor_server_map = await _build_vendor_server_map(server_ids)

    # births
    pregnancies = await list_pooch_pregnancies()
    for pregnancy in pregnancies:
        mother_id = int(pregnancy.mother_id)
        fetus_id = int(pregnancy.fetus_id)

        await delete_pregnancy(mother_id, fetus_id)

        mother = await db_get_pooch_by_id(mother_id)
        if mother is None:
            continue

        server_id = _resolve_server_id(mother, vendor_server_map, server_ids)

        baby = await create_pooch(owner_discord_id=mother.owner_discord_id)

        kennel = await get_pooch_kennel(mother_id)
        if kennel is not None:
            await add_pooch_to_kennel(int(kennel.id), int(baby.id))

        if server_id is not None:
            server_ids.add(server_id)
            births_by_server.setdefault(server_id, []).append(
                BirthEvent(server_id=server_id, mother_id=mother_id, child_id=int(baby.id))
            )

    # deaths (and other updates)
    pooches = await list_living_pooches()
    for pooch in pooches:
        pooch_id = int(pooch.id)

        server_id = _resolve_server_id(pooch, vendor_server_map, server_ids)
        if server_id is not None:
            server_ids.add(server_id)

        await decrement_pooch_breeding_cooldown(pooch_id)
        updated = await age_pooch(pooch_id)
        if updated is None:
            continue

        total_health = max(int(updated.base_health) - int(updated.health_loss_age), 0)
        if _death_roll(total_health, rng):
            await set_pooch_dead(pooch_id)
            await remove_pooch_from_kennel(pooch_id)
            if pooch.owner_discord_id is not None:
                await bury_pooch(int(pooch.owner_discord_id), pooch_id)
            if server_id is not None:
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
            await clear_vendor_pooch_stock(vendor_id)
            stock_n = rng.randint(2, 5)
            for _ in range(stock_n):
                vendor_pooch = await create_pooch(vendor_id=vendor_id)
                await add_pooch_to_vendor_stock(vendor_id, int(vendor_pooch.id))

    # summaries (always emit one per server)
    out: dict[int, DayChangeSummary] = {}
    for server_id in sorted(server_ids):
        out[server_id] = DayChangeSummary(
            server_id=server_id,
            births=births_by_server.get(server_id, []),
            deaths=deaths_by_server.get(server_id, []),
        )
    return out
