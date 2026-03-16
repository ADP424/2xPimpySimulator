from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

import numpy

from src.database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    add_pooch_to_strays,
    add_pooch_to_vendor_stock,
    age_pooch,
    bury_pooch,
    clear_vendor_pooch_stock,
    create_pooch,
    create_vendor,
    decrement_pooch_breeding_cooldown,
    delete_pregnancy,
    delete_random_vendor,
    get_mutation_health_impact,
    get_pooch_health,
    get_pooch_kennel,
    list_living_pooches,
    list_pooch_mutations,
    list_pooch_pregnancies,
    list_pooches_for_kennel,
    list_servers,
    list_servers_for_pooch,
    list_strays_for_server,
    list_vendors,
    remove_pooch_from_kennel,
    reset_begged_today,
    reset_visited_park_today,
    set_pooch_breeding_cooldown,
    set_pooch_dead,
)
from src.logger import get_logger

from .constants import (
    DEATH_CHANCE_PER_HEALTH_UNDER_MIN,
    MIN_HEALTH_FOR_DEATH_CHANCE,
    NUM_BREEDS_PER_VENDOR_POOCH_RANGE,
    NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE,
    NUM_VENDORS_PER_SERVER,
    POOCH_BASE_HEALTH_RANGE,
    POOCH_BREEDING_COOLDOWN,
    POOCH_HEALTH_LOSS_STARTING_AGE,
    VENDOR_MARKUP_RANGE,
    VENDOR_POOCH_AGE_RANGE,
    VENDOR_POOCH_STOCK_COUNT_RANGE,
)
from .manage_kennels import add_pooch_to_kennel
from .manage_pooches import get_pooch_by_id
from .manage_stray_events import run_daily_stray_event_check
from .models import (
    BirthEvent,
    DayChangeSummary,
    DeathEvent,
    OtherEvent,
    to_pooch,
    to_server,
)

if TYPE_CHECKING:
    from src.database.models import Mutation, Pooch

from .utils import get_pooch_mutation_advanced_option_total

logger = get_logger("game/change_day")


def _death_roll(total_health: int, rng: random.Random) -> bool:
    """
    Randomly determine whether a Pooch should die or not, based on its health.
    """

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
    numpy_rng = numpy.random.default_rng(rng_seed)

    # reset daily owner actions
    await reset_begged_today()
    await reset_visited_park_today()

    births_by_server: dict[int, list[BirthEvent]] = {}
    deaths_by_server: dict[int, list[DeathEvent]] = {}
    other_events_by_server: dict[int, list[OtherEvent]] = {}

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
                        message="The mother doesn't belong to a kennel. Her baby was abandoned.",
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
                        message=(
                            f"There wasn't enough space in {mother.name}'s kennel. "
                            f"Her baby, {baby.name}, was crushed."
                        ),
                    )
                )
            continue

        for server in servers:
            births_by_server.setdefault(server.discord_id, []).append(
                BirthEvent(
                    server=(await to_server(server)),
                    mother=(await to_pooch(mother)),
                    child=(await to_pooch(baby)),
                    message=f"{mother.name} gave birth to {baby.name}.",
                )
            )
    logger.info("Completed daily births.")

    # deaths (and other updates)
    logger.info("Handling deaths for the day...")

    async def _kill_pooch(pooch: Pooch) -> Pooch:
        pooch = await set_pooch_dead(pooch.id)
        await remove_pooch_from_kennel(pooch.id)
        if pooch.owner_discord_id is not None:
            await bury_pooch(pooch.owner_discord_id, pooch.id)
        return pooch

    pooches = await list_living_pooches()
    for pooch in pooches:
        pooch = await decrement_pooch_breeding_cooldown(pooch.id)
        pooch = await age_pooch(pooch.id, POOCH_HEALTH_LOSS_STARTING_AGE)
        total_health: int = await get_pooch_health(pooch.id)

        if not pooch.alive:
            continue

        if _death_roll(total_health, rng):
            pooch = await _kill_pooch(pooch)
            pooch_mutations = await list_pooch_mutations(pooch.id)
            negative_pooch_mutations = await list_pooch_mutations(pooch.id, positive=False, neutral=False)

            negative_health_impacts = [
                await get_mutation_health_impact(mutation.id) for mutation in negative_pooch_mutations
            ]
            negative_health_impacts = [
                health_impact for health_impact in negative_health_impacts if health_impact is not None
            ]
            if negative_health_impacts:
                total_health_impact = sum(negative_health_impacts)
                death_cause: Mutation = (
                    numpy_rng.choice(
                        negative_pooch_mutations,
                        p=[(health_impact / total_health_impact) for health_impact in negative_health_impacts],
                    )
                    if negative_pooch_mutations
                    else None
                )
                death_message = death_cause.advanced_options.get("death_message", f"{pooch.name} died.").replace(
                    "[pooch]", pooch.name
                )
            elif pooch.health_loss_age > 0:
                death_message = f"{pooch.name} died of old age."
            else:
                death_message = f"{pooch.name} died of unknown causes."

            for server in await list_servers_for_pooch(pooch.id):
                deaths_by_server.setdefault(server.discord_id, []).append(
                    DeathEvent(server=(await to_server(server)), pooch=(await to_pooch(pooch)), message=death_message)
                )

            for pooch_mutation in pooch_mutations:
                on_death: Optional[str] = pooch_mutation.advanced_options.get("on_death", "none").lower()
                always_on_death = bool(pooch_mutation.advanced_options.get("on_death", 0))
                on_death_chance: float = pooch_mutation.advanced_options.get("on_death_chance", 1.0)

                if (
                    on_death == "none"
                    or (not always_on_death and pooch_mutation.id != death_cause.id)
                    or rng.random() > on_death_chance
                ):
                    continue

                on_death_targets: str = pooch_mutation.advanced_options.get("on_death_targets", "none").lower()

                target_pooches: list[Pooch] = []
                if on_death_targets == "all":
                    pooch_kennel = await get_pooch_kennel(pooch.id)
                    if pooch_kennel is None:
                        continue
                    target_pooches = [
                        kennel_pooch
                        for kennel_pooch in (await list_pooches_for_kennel(pooch_kennel.id))
                        if kennel_pooch.alive and kennel_pooch.id != pooch.id
                    ]
                elif on_death_targets == "random":
                    pooch_kennel = await get_pooch_kennel(pooch.id)
                    if pooch_kennel is None:
                        continue
                    target_pooches = [
                        rng.choice(
                            [
                                kennel_pooch
                                for kennel_pooch in (await list_pooches_for_kennel(pooch_kennel.id))
                                if kennel_pooch.alive and kennel_pooch.id != pooch.id
                            ]
                        )
                    ]

                if on_death == "kill":
                    for target in target_pooches:
                        await _kill_pooch(target)
                        death_message = (
                            pooch_mutation.advanced_options.get(
                                "impact_message", f"{target.name} died from {pooch.name}'s {pooch_mutation.name}."
                            )
                            .replace("[pooch]", pooch.name)
                            .replace("[victim]", target.name)
                        )
                        for server in await list_servers_for_pooch(target.id):
                            deaths_by_server.setdefault(server.discord_id, []).append(
                                DeathEvent(
                                    server=(await to_server(server)),
                                    pooch=(await to_pooch(target)),
                                    message=death_message,
                                )
                            )
                elif on_death == "spread":
                    for target in target_pooches:
                        await add_mutation_to_pooch(target.id, pooch_mutation.id)
                        target = await get_pooch_by_id(target.id)
                        spread_message = (
                            pooch_mutation.advanced_options.get(
                                "impact_message",
                                f"{pooch.name} spread its {pooch_mutation.name} to {target.name} as they died.",
                            )
                            .replace("[pooch]", pooch.name)
                            .replace("[victim]", target.name)
                        )
                        for server in await list_servers_for_pooch(target.id):
                            other_events_by_server.setdefault(server.discord_id, []).append(
                                OtherEvent(
                                    server=(await to_server(server)),
                                    pooch=(await to_pooch(target)),
                                    message=spread_message,
                                )
                            )
                elif on_death == "spread_all":
                    for target in target_pooches:
                        for mutation in pooch_mutations:
                            await add_mutation_to_pooch(target.id, mutation.id)
                        target = await get_pooch_by_id(target.id)
                        spread_message = (
                            pooch_mutation.advanced_options.get(
                                "impact_message",
                                (
                                    f"{pooch.name} spread ALL its mutations to {target.name} as they died, "
                                    f"because of its {pooch_mutation.name}."
                                ),
                            )
                            .replace("[pooch]", pooch.name)
                            .replace("[victim]", target.name)
                        )
                        for server in await list_servers_for_pooch(target.id):
                            other_events_by_server.setdefault(server.discord_id, []).append(
                                OtherEvent(
                                    server=(await to_server(server)),
                                    pooch=(await to_pooch(target)),
                                    message=spread_message,
                                )
                            )

    logger.info("Completed daily deaths.")

    servers = await list_servers()

    # minimum stray guarantee: every server must have at least one alive stray
    logger.info("Checking minimum stray population per server...")
    for server in servers:
        strays = await list_strays_for_server(server.discord_id)
        if not strays:
            stray_pooch = await create_pooch(
                base_health=rng.randint(POOCH_BASE_HEALTH_RANGE[0], POOCH_BASE_HEALTH_RANGE[1]),
                age=0,
                rng=rng,
            )
            if stray_pooch:
                await add_pooch_to_strays(stray_pooch.id, server.discord_id)
                logger.info(f"Added guaranteed stray pooch {stray_pooch.id} to server {server.discord_id}.")
    logger.info("Minimum stray check complete.")

    # stray events (fire once per server after the stray population is guaranteed)
    logger.info("Running daily stray events...")
    await run_daily_stray_event_check(rng_seed=rng.randint(0, 2**31))
    logger.info("Completed daily stray events.")

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
        for vendor in vendors:
            await clear_vendor_pooch_stock(vendor.id, delete_pooches=True)
            stock_count = rng.randint(VENDOR_POOCH_STOCK_COUNT_RANGE[0], VENDOR_POOCH_STOCK_COUNT_RANGE[1])
            for _ in range(stock_count):
                vendor_pooch = await create_pooch(
                    vendor_id=vendor.id,
                    age=rng.randint(VENDOR_POOCH_AGE_RANGE[0], VENDOR_POOCH_AGE_RANGE[1]),
                    base_health=rng.randint(POOCH_BASE_HEALTH_RANGE[0], POOCH_BASE_HEALTH_RANGE[1]),
                    rng=rng,
                )
                await set_pooch_breeding_cooldown(
                    vendor_pooch.id,
                    (
                        max(
                            POOCH_BREEDING_COOLDOWN
                            + await get_pooch_mutation_advanced_option_total(vendor_pooch.id, "breeding_cooldown"),
                            0,
                        )
                    )
                    // 2,  # Make the breeding cooldown half to start with for vendor pooches
                )
                num_breeds = rng.randint(NUM_BREEDS_PER_VENDOR_POOCH_RANGE[0], NUM_BREEDS_PER_VENDOR_POOCH_RANGE[1])
                for _ in range(num_breeds):
                    await add_breed_to_pooch(vendor_pooch.id, weight=(1.0 / num_breeds), from_vendor=True)
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
            other_events=other_events_by_server.get(server.discord_id, []),
        )
    return out
