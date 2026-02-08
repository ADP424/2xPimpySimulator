import random
from typing import Dict, List, Optional

from .model import BirthEvent, DeathEvent, DayChangeSummary
from .manage_pooches import get_pooch_by_id

from database import (
    list_alive_player_pooches_all_servers,
    list_pregnancies,
    delete_pregnancy,
    get_pooch_kennel,
    create_newborn_pooch,
    add_pooch_to_kennel,
    decrement_breeding_cooldown,
    age_pooch,
    remove_pooch_from_kennels,
    set_pooch_dead,
    bury_pooch,
    list_vendors,
    clear_vendor_stock,
    add_vendor_stock,
)


def _death_roll(total_health: int, rng: random.Random) -> bool:
    if total_health >= 5:
        return False
    deficit = 5 - max(total_health, 0)
    chance = min(0.2 * deficit, 1.0)
    return rng.random() < chance


def _random_sex(rng: random.Random) -> str:
    return rng.choice(["M", "F"])


def _random_name(rng: random.Random) -> str:
    return rng.choice(["Poochlet", "Muttling", "Pup", "Bean", "Nugget"])


async def run_day_change(rng_seed: Optional[int] = None) -> Dict[int, DayChangeSummary]:
    rng = random.Random(rng_seed)

    births_by_server: Dict[int, List[BirthEvent]] = {}
    deaths_by_server: Dict[int, List[DeathEvent]] = {}

    # births
    pregnancies = await list_pregnancies()
    for pregnancy in pregnancies:
        server_id = int(pregnancy.server_id)
        mother_id = int(pregnancy.mother_id)
        fetus_id = int(pregnancy.fetus_id)

        await delete_pregnancy(server_id, mother_id, fetus_id)

        mother = await get_pooch_by_id(server_id, mother_id)
        baby = await create_newborn_pooch(
            server_id=server_id,
            owner_discord_id=mother.owner_discord_id,
            name=_random_name(rng),
            sex=_random_sex(rng),
            base_health=rng.randint(8, 12),
        )

        kennel_id = await get_pooch_kennel(server_id, mother_id)
        if kennel_id is not None:
            await add_pooch_to_kennel(server_id, kennel_id, int(baby.id))

        births_by_server.setdefault(server_id, []).append(
            BirthEvent(server_id=server_id, mother_id=mother_id, child_id=int(baby.id))
        )

    # deaths (and other updates)
    pooches = await list_alive_player_pooches_all_servers()
    servers = set(int(p.server_id) for p in pooches)

    for pooch in pooches:
        server_id = int(pooch.server_id)
        pooch_id = int(pooch.id)

        await decrement_breeding_cooldown(server_id, pooch_id)
        updated = await age_pooch(server_id, pooch_id)
        if updated is None:
            continue

        game_pooch = await get_pooch_by_id(server_id, pooch_id)
        if _death_roll(game_pooch.health, rng):
            await set_pooch_dead(server_id, pooch_id)
            await remove_pooch_from_kennels(server_id, pooch_id)
            if game_pooch.owner_discord_id is not None:
                await bury_pooch(server_id, int(game_pooch.owner_discord_id), pooch_id)
            deaths_by_server.setdefault(server_id, []).append(DeathEvent(server_id=server_id, pooch_id=pooch_id))

    # vendor restock
    for server_id in list(servers | births_by_server.keys() | deaths_by_server.keys()):
        for v in await list_vendors(server_id):
            vid = int(v.id)
            await clear_vendor_stock(server_id, vid)
            stock_n = rng.randint(2, 5)
            for _ in range(stock_n):
                vp = await create_newborn_pooch(
                    server_id=server_id,
                    owner_discord_id=None,
                    name=_random_name(rng),
                    sex=_random_sex(rng),
                    base_health=rng.randint(8, 12),
                )
                await add_vendor_stock(server_id, vid, int(vp.id), rng.randint(50, 150))

    # summaries
    out: Dict[int, DayChangeSummary] = {}
    for server_id in list(servers | births_by_server.keys() | deaths_by_server.keys()):
        out[server_id] = DayChangeSummary(
            server_id=server_id,
            births=births_by_server.get(server_id, []),
            deaths=deaths_by_server.get(server_id, []),
        )
    return out
