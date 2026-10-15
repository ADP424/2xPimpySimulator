from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_injury_to_pooch,
    add_mutation_to_pooch,
    add_pooch_to_strays,
)
from src.database import age_pooch as db_age_pooch
from src.database import (
    bury_pooch,
    close_auction_sale_listing,
    damn_pooch,
    decrement_pooch_pregnancy_timer,
    delete_pregnancy,
    get_active_auction_sale_listing_for_pooch,
    get_current_season,
    get_disease_health_impact,
    get_injury_by_name,
    get_injury_health_impact,
    get_mutation_health_impact,
    get_pooch_by_id,
    get_pooch_kennel,
    give_money_to_owner,
    increment_global_hour,
    list_bids_for_listing,
    list_living_pooches,
    list_pooch_diseases,
    list_pooch_injuries,
    list_pooch_mutations,
    list_pooch_pregnancies,
    list_pooches_for_kennel,
    list_servers,
    list_servers_for_pooch,
    modify_kennel_food_stock,
    modify_pooch_age,
    modify_pooch_starvation,
    remove_pooch_from_kennel,
    reset_pooch_breeding_cooldown,
    set_pooch_birth_hour,
    set_pooch_dead,
    set_pooch_pregnancy_timer,
    update_pooch_mood,
)
from src.logger import get_logger

from .change_day import _pick_mood
from .constants import (
    CANNIBALISM_GUILT_INJURY,
    CANNIBALISM_HOURLY_BASE_CHANCE,
    CANNIBALISM_STARVATION_MULTIPLIER,
    HOURLY_DEATH_CHANCE_PER_HEALTH_UNDER_MIN,
    HOURLY_FIGHT_AGGRESSION_SCALE,
    HOURLY_FIGHT_BASE_CHANCE,
    HOURLY_FIGHT_HEALTH_PENALTY,
    HOURLY_FIGHT_STARVATION_SCALE,
    MIN_HEALTH_FOR_DEATH_CHANCE,
    MISCARRIAGE_HOURLY_BASE_CHANCE,
    POOCH_BREEDING_COOLDOWN,
    POOCH_HEALTH_LOSS_STARTING_AGE,
    STARVATION_DECAY_PER_FED_HOUR,
    STILLBIRTH_BASE_CHANCE,
)
from .events.shared import handle_fight_pooches
from .manage_diseases import run_hourly_disease_tick
from .manage_hell import drop_body_parts
from .manage_kennels import add_pooch_to_kennel
from .manage_pooches import (
    run_hourly_breeding_cooldown_check,
    run_hourly_injury_persistence_check,
)
from .manage_stats import get_effective_stats, get_pooch_health
from .models import (
    BirthEvent,
    DeathEvent,
    HourChangeSummary,
    OtherEvent,
    to_pooch,
    to_server,
)
from .utils.on_death_effects import apply_on_death_injure
from .utils.pronouns import substitute_placeholders

if TYPE_CHECKING:
    from src.database.models import Pooch

logger = get_logger("game/change_hour")


# ---------------------------------------------------------------------------
# Death roll — hourly rate is 1/N of daily.
# ---------------------------------------------------------------------------


def hourly_death_roll(total_health: int, rng: random.Random, *, immortal: bool = False) -> bool:
    """
    Roll whether a pooch dies this hour based on its current health.

    Immortal pooches still take damage from injuries/mutations and can die
    if their health hits 0, but they never roll death from age-related health
    loss alone (this is enforced by never incrementing health_loss_age for
    immortal pooches in ``hourly_age_step``).

    Parameters
    ----------
    total_health:
        Effective health including mutation/injury/disease impacts.
    rng:
        Seeded Random.
    immortal:
        If True, the death roll is skipped unless health <= 0.
    """
    if total_health <= 0:
        return True
    if total_health >= MIN_HEALTH_FOR_DEATH_CHANCE:
        return False
    if immortal:
        return False
    deficit = MIN_HEALTH_FOR_DEATH_CHANCE - max(total_health, 0)
    hourly_chance = min(HOURLY_DEATH_CHANCE_PER_HEALTH_UNDER_MIN * deficit, 1.0)
    return rng.random() < hourly_chance


# ---------------------------------------------------------------------------
# Helper: kill a pooch (handles graveyard move, auction refund, kennel remove)
# ---------------------------------------------------------------------------


async def _kill_pooch(pooch: "Pooch") -> "Pooch":
    pooch = await set_pooch_dead(pooch.id)
    await remove_pooch_from_kennel(pooch.id)
    if pooch.owner_discord_id is not None:
        await bury_pooch(pooch.owner_discord_id, pooch.id)
    listing = await get_active_auction_sale_listing_for_pooch(pooch.id)
    if listing is not None:
        bids = await list_bids_for_listing(listing.id)
        refunded: set[int] = set()
        for bid in bids:
            if bid.bidder_discord_id not in refunded:
                await give_money_to_owner(bid.bidder_discord_id, bid.amount)
                refunded.add(bid.bidder_discord_id)
        await close_auction_sale_listing(listing.id, None, None)
    return pooch


# ---------------------------------------------------------------------------
# Helper: body-part drops on violent death
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Per-hour aging: increment age on 24-hour birth anniversary
# ---------------------------------------------------------------------------


async def hourly_age_step(current_hour: int, pooch: "Pooch") -> bool:
    """
    Increment ``pooch.age`` if ``current_hour`` is exactly 24 hours past its
    ``birth_hour`` boundary. Fetal pooches (age == -1) never age here.
    Immortal pooches still age but never accrue health_loss_age.

    Returns True if the pooch aged this hour.
    """
    if pooch.age < 0:
        return False
    birth_hour = pooch.birth_hour
    if birth_hour is None:
        # Pooches created before the hour-loop migration: seed birth_hour now
        # and skip this tick.
        await set_pooch_birth_hour(pooch.id, current_hour)
        return False
    elapsed = current_hour - int(birth_hour)
    if elapsed <= 0 or elapsed % 24 != 0:
        return False

    # Age up. Apply health_loss_age via the existing age_pooch path unless immortal.
    if pooch.immortal:
        # Immortals age but take no age-based health loss.
        await modify_pooch_age(pooch.id, 1)
    else:
        await db_age_pooch(pooch.id, POOCH_HEALTH_LOSS_STARTING_AGE)
    logger.debug("Pooch %s (%d) aged to %d", pooch.name, pooch.id, pooch.age + 1)
    return True


# ---------------------------------------------------------------------------
# Pregnancy: timer decrement → birth on 0, with stillbirth roll
# ---------------------------------------------------------------------------


def _miscarriage_chance(
    pooch: "Pooch",
    stats: dict[str, int],
    *,
    rng: random.Random,
) -> float:
    """Hourly miscarriage chance. ``stats`` are the mother's effective stats."""
    base = MISCARRIAGE_HOURLY_BASE_CHANCE
    # Old mothers → higher miscarriage.
    if pooch.age and pooch.age > 5:
        base *= 1.0 + 0.2 * (pooch.age - 5)
    # Low constitution → higher.
    const = max(1, int(stats.get("constitution", 10) or 10))
    base *= 10 / const
    # Starvation multiplier
    base *= 1.0 + 0.05 * int(pooch.starvation or 0)
    return min(0.8, max(0.0, base))


def _stillbirth_chance(mother: "Pooch", stats: dict[str, int], *, rng: random.Random) -> float:
    """Stillbirth chance per delivery. ``stats`` are the mother's effective stats."""
    base = STILLBIRTH_BASE_CHANCE
    if mother.age and mother.age > 5:
        base *= 1.0 + 0.2 * (mother.age - 5)
    const = max(1, int(stats.get("constitution", 10) or 10))
    base *= 10 / const
    base *= 1.0 + 0.05 * int(mother.starvation or 0)
    return min(0.8, max(0.0, base))


async def _handle_birth(
    mother: "Pooch",
    fetus: "Pooch",
    mother_stats: dict[str, int],
    *,
    rng: random.Random,
    births_by_server: dict,
    deaths_by_server: dict,
):
    """Deliver a single fetus. Handles stillbirth roll + kennel placement."""

    await delete_pregnancy(mother.id, fetus.id)

    # Stillbirth roll.
    if rng.random() < _stillbirth_chance(mother, mother_stats, rng=rng):
        fetus = await modify_pooch_age(fetus.id, 1)  # -1 -> 0
        await _kill_pooch(fetus)
        for server in await list_servers_for_pooch(fetus.id):
            deaths_by_server.setdefault(server.discord_id, []).append(
                DeathEvent(
                    server=(await to_server(server)),
                    pooch=(await to_pooch(fetus)),
                    message=f"{fetus.name} was stillborn.",
                )
            )
        return

    # Normal birth: increment age to 0.
    fetus = await modify_pooch_age(fetus.id, 1)

    kennel = await get_pooch_kennel(mother.id)
    if kennel is None:
        baby_health = await get_pooch_health(fetus.id)
        await update_pooch_mood(fetus.id, _pick_mood(baby_health, fetus.age, rng))
        for server in await list_servers_for_pooch(fetus.id):
            births_by_server.setdefault(server.discord_id, []).append(
                BirthEvent(
                    server=(await to_server(server)),
                    mother=(await to_pooch(mother)),
                    child=(await to_pooch(fetus)),
                    message="The mother doesn't belong to a kennel. Her baby was abandoned.",
                )
            )
        return

    success = await add_pooch_to_kennel(kennel.id, fetus.id)
    if not success:
        await update_pooch_mood(fetus.id, "dead")
        for server in await list_servers_for_pooch(fetus.id):
            await add_pooch_to_strays(fetus.id, server.discord_id)
            births_by_server.setdefault(server.discord_id, []).append(
                BirthEvent(
                    server=(await to_server(server)),
                    mother=(await to_pooch(mother)),
                    child=(await to_pooch(fetus)),
                    message=(
                        f"There wasn't enough space in {mother.name}'s kennel. "
                        f"Her baby, {fetus.name}, was released as a stray."
                    ),
                )
            )
        return

    baby_health = await get_pooch_health(fetus.id)
    await update_pooch_mood(fetus.id, _pick_mood(baby_health, fetus.age, rng))
    for server in await list_servers_for_pooch(fetus.id):
        births_by_server.setdefault(server.discord_id, []).append(
            BirthEvent(
                server=(await to_server(server)),
                mother=(await to_pooch(mother)),
                child=(await to_pooch(fetus)),
                message=f"{mother.name} gave birth to {fetus.name}.",
            )
        )


async def _handle_miscarriage(
    mother: "Pooch",
    fetus: "Pooch",
    *,
    deaths_by_server: dict,
):
    await delete_pregnancy(mother.id, fetus.id)
    fetus = await set_pooch_dead(fetus.id)
    if mother.owner_discord_id is not None:
        await bury_pooch(mother.owner_discord_id, fetus.id)
    await reset_pooch_breeding_cooldown(mother.id, POOCH_BREEDING_COOLDOWN)
    for server in await list_servers_for_pooch(fetus.id):
        deaths_by_server.setdefault(server.discord_id, []).append(
            DeathEvent(
                server=(await to_server(server)),
                pooch=(await to_pooch(fetus)),
                message=f"{mother.name} suffered a miscarriage.",
            )
        )


# ---------------------------------------------------------------------------
# Food / starvation tick
# ---------------------------------------------------------------------------


async def _hourly_food_tick(
    kennel,
    living_pooches: list["Pooch"],
) -> list[tuple["Pooch", int]]:
    """
    Consume food from ``kennel.food_stock`` to feed each living pooch's
    hourly consumption. Unmet demand raises the pooch's starvation counter.
    Returns (pooch, starvation_delta) tuples for pooches that changed state.
    """
    updates: list[tuple["Pooch", int]] = []
    for pooch in living_pooches:
        need = int(pooch.consumption or 1)
        if need <= 0:
            continue
        # Feed what we can.
        stock_before = int(kennel.food_stock or 0)
        consumed = min(need, stock_before)
        if consumed > 0:
            new_stock = await modify_kennel_food_stock(kennel.id, -consumed)
            kennel.food_stock = new_stock if new_stock is not None else max(0, stock_before - consumed)
        shortfall = need - consumed
        if shortfall > 0:
            await modify_pooch_starvation(pooch.id, shortfall)
            updates.append((pooch, shortfall))
        elif consumed >= need and int(pooch.starvation or 0) > 0:
            await modify_pooch_starvation(pooch.id, -STARVATION_DECAY_PER_FED_HOUR)
            updates.append((pooch, -STARVATION_DECAY_PER_FED_HOUR))
    return updates


# ---------------------------------------------------------------------------
# Hourly fight roll
# ---------------------------------------------------------------------------


def _cannibalism_chance(pooch: "Pooch") -> float:
    """Hourly chance a pooch eats a kennel-mate. Only starving pooches do it, more often the hungrier they are."""
    starvation = int(pooch.starvation or 0)
    if starvation <= 0:
        return 0.0
    return min(1.0, CANNIBALISM_HOURLY_BASE_CHANCE + CANNIBALISM_STARVATION_MULTIPLIER * starvation)


def _hourly_fight_chance(pooch: "Pooch", stats: dict[str, int]) -> float:
    """Hourly chance a pooch picks a fight. ``stats`` are its effective stats."""
    agg = max(0, int(stats.get("aggressiveness", 10) or 10) - 10)
    health = int(stats.get("base_health", 10) or 10)
    starvation = int(pooch.starvation or 0)
    chance = HOURLY_FIGHT_BASE_CHANCE
    chance += HOURLY_FIGHT_AGGRESSION_SCALE * agg
    chance += HOURLY_FIGHT_STARVATION_SCALE * starvation
    if health < 5:
        chance *= HOURLY_FIGHT_HEALTH_PENALTY
    return max(0.0, min(0.1, chance))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_hour_change(rng_seed: Optional[int] = None) -> dict[int, HourChangeSummary]:
    """
    Run one hour of game time. Returns a per-server summary dict.

    The caller (the bot scheduler or a test) should only post summaries that
    are not ``is_empty`` to the user-facing event channel.
    """
    rng = random.Random(rng_seed)

    current_hour = await increment_global_hour()

    births_by_server: dict[int, list[BirthEvent]] = {}
    deaths_by_server: dict[int, list[DeathEvent]] = {}
    other_events_by_server: dict[int, list[OtherEvent]] = {}

    season = await get_current_season()

    # 1. Pregnancy tick (miscarriage or birth)
    pregnancies = await list_pooch_pregnancies()
    pregnancy_by_mother: dict[int, list[int]] = {}
    for pregnancy in pregnancies:
        pregnancy_by_mother.setdefault(pregnancy.mother_id, []).append(pregnancy.fetus_id)

    for mother_id, fetus_ids in pregnancy_by_mother.items():
        mother = await get_pooch_by_id(mother_id)
        if mother is None or not mother.alive:
            continue
        mother_stats = await get_effective_stats(mother.id)
        # Miscarriage roll first
        if rng.random() < _miscarriage_chance(mother, mother_stats, rng=rng):
            for fid in fetus_ids:
                fetus = await get_pooch_by_id(fid)
                if fetus is not None:
                    await _handle_miscarriage(mother, fetus, deaths_by_server=deaths_by_server)
            await set_pooch_pregnancy_timer(mother.id, None)
            continue

        # Decrement timer
        new_timer = await decrement_pooch_pregnancy_timer(mother.id)
        if new_timer is None or new_timer > 0:
            continue

        # Birth!
        for fid in fetus_ids:
            fetus = await get_pooch_by_id(fid)
            if fetus is None:
                continue
            await _handle_birth(
                mother,
                fetus,
                mother_stats,
                rng=rng,
                births_by_server=births_by_server,
                deaths_by_server=deaths_by_server,
            )
        await set_pooch_pregnancy_timer(mother.id, None)
        await reset_pooch_breeding_cooldown(mother.id, POOCH_BREEDING_COOLDOWN)

    # 2. Aging step for each living pooch (every 24 hours past birth_hour)
    pooches = await list_living_pooches()
    for pooch in pooches:
        await hourly_age_step(current_hour, pooch)

    # 3. Hourly fertility/breeding cooldown tick
    await run_hourly_breeding_cooldown_check(rng_seed=rng_seed)

    # 4. Hourly injury persistence tick
    await run_hourly_injury_persistence_check(rng_seed=rng_seed)

    # 5. Disease tick (for kennel pooches and strays).
    disease_events = await run_hourly_disease_tick(season=season, rng_seed=rng_seed)
    for pooch_id, pooch_events in disease_events.items():
        pooch_orm = await get_pooch_by_id(pooch_id)
        if pooch_orm is None:
            continue
        for _disease_id, public_label, event_type in pooch_events:
            if event_type == "contracted":
                msg = f"{pooch_orm.name} started showing signs of {public_label}."
            elif event_type == "spread":
                msg = f"{pooch_orm.name} caught {public_label} from a kennel mate."
            elif event_type == "recovered":
                msg = f"{pooch_orm.name} recovered from {public_label}."
            else:
                msg = f"{pooch_orm.name} was affected by {public_label}."
            for server in await list_servers_for_pooch(pooch_id):
                other_events_by_server.setdefault(server.discord_id, []).append(
                    OtherEvent(
                        server=(await to_server(server)),
                        pooch=(await to_pooch(pooch_orm)),
                        message=msg,
                    )
                )

    # 6. Food/starvation tick per kennel (also eats into food_stock).
    # Note: food stock tick is done as part of this loop.
    kennels_seen: set[int] = set()
    for pooch in pooches:
        kennel = await get_pooch_kennel(pooch.id)
        if kennel is None or kennel.id in kennels_seen:
            continue
        kennels_seen.add(kennel.id)
        living_in_kennel = [p for p in (await list_pooches_for_kennel(kennel.id)) if p.alive]
        if not living_in_kennel:
            continue
        await _hourly_food_tick(kennel, living_in_kennel)

    # 7. Hourly fight rolls (a pooch may pick a fight with a kennel-mate)
    for pooch in pooches:
        pooch = await get_pooch_by_id(pooch.id)
        if pooch is None or not pooch.alive:
            continue
        kennel = await get_pooch_kennel(pooch.id)
        if kennel is None:
            continue
        chance = _hourly_fight_chance(pooch, await get_effective_stats(pooch.id))
        if chance <= 0 or rng.random() > chance:
            continue
        mates = [p for p in (await list_pooches_for_kennel(kennel.id)) if p.alive and p.id != pooch.id]
        if not mates:
            continue
        target = rng.choice(mates)
        result = await handle_fight_pooches(pooch.id, target.id, rng=rng)
        msg = f"{pooch.name} picked a fight with {target.name}."
        for server in await list_servers_for_pooch(pooch.id):
            other_events_by_server.setdefault(server.discord_id, []).append(
                OtherEvent(
                    server=(await to_server(server)),
                    pooch=(await to_pooch(pooch)),
                    message=msg,
                )
            )
        # If the loser died, drop body parts to the winner's owner.
        winner_id = result.get("winner_id")
        loser = target if result.get("defender_died") else pooch if result.get("attacker_died") else None
        if loser is not None and winner_id is not None:
            winner = await get_pooch_by_id(winner_id)
            if winner is not None and winner.owner_discord_id is not None:
                await drop_body_parts(winner.owner_discord_id, loser, rng, scale=0.5)

    # 8. Cannibalism: a starving pooch may eat a kennel-mate, sating its hunger and leaving it guilt-ridden
    for pooch in pooches:
        pooch = await get_pooch_by_id(pooch.id)
        if pooch is None or not pooch.alive:
            continue
        if rng.random() >= _cannibalism_chance(pooch):
            continue
        kennel = await get_pooch_kennel(pooch.id)
        if kennel is None:
            continue
        victims = [
            p for p in (await list_pooches_for_kennel(kennel.id)) if p.alive and p.id != pooch.id and not p.immortal
        ]
        if not victims:
            continue
        victim = rng.choice(victims)
        victim_servers = await list_servers_for_pooch(victim.id)
        victim = await _kill_pooch(victim)
        await update_pooch_mood(victim.id, "dead")
        await modify_pooch_starvation(pooch.id, -int(pooch.starvation or 0))
        guilt = await get_injury_by_name(CANNIBALISM_GUILT_INJURY)
        if guilt is not None:
            await add_injury_to_pooch(pooch.id, guilt.id)
        for server in victim_servers:
            deaths_by_server.setdefault(server.discord_id, []).append(
                DeathEvent(
                    server=(await to_server(server)),
                    pooch=(await to_pooch(victim)),
                    message=f"{victim.name} was eaten by {pooch.name}, who had been starving.",
                )
            )

    # 9. Death rolls (reduced rate).
    for pooch in pooches:
        pooch = await get_pooch_by_id(pooch.id)
        if pooch is None or not pooch.alive:
            continue
        total_health = await get_pooch_health(pooch.id)
        if hourly_death_roll(total_health, rng, immortal=bool(pooch.immortal)):
            pooch_kennel_before_death = await get_pooch_kennel(pooch.id)
            pooch = await _kill_pooch(pooch)
            await update_pooch_mood(pooch.id, "dead")
            pooch_mutations = await list_pooch_mutations(pooch.id)

            death_cause = None
            death_message = f"{pooch.name} died."

            # Build the death-cause pool.
            pool_candidates = []
            pool_weights = []
            neg_mutations = await list_pooch_mutations(pooch.id, positive=False, neutral=False)
            for m in neg_mutations:
                impact = await get_mutation_health_impact(m.id)
                if impact is not None and impact < 0:
                    pool_candidates.append(m)
                    pool_weights.append(abs(impact))
            num_mutation_candidates = len(pool_candidates)
            pooch_injuries = await list_pooch_injuries(pooch.id)
            for inj in pooch_injuries:
                impact = await get_injury_health_impact(inj.id)
                if impact is not None and impact < 0:
                    pool_candidates.append(inj)
                    pool_weights.append(abs(impact))
            pooch_diseases = await list_pooch_diseases(pooch.id)
            for d in pooch_diseases:
                impact = await get_disease_health_impact(d.id)
                if impact is not None and impact < 0:
                    pool_candidates.append(d)
                    pool_weights.append(abs(impact))
            if pooch.health_loss_age > 0 and not pooch.immortal:
                pool_candidates.append("old_age")
                pool_weights.append(pooch.health_loss_age)

            if pool_candidates:
                idx = rng.choices(range(len(pool_candidates)), weights=pool_weights, k=1)[0]
                chosen = pool_candidates[idx]
                if chosen == "old_age":
                    death_message = f"{pooch.name} died of old age."
                else:
                    if idx < num_mutation_candidates:
                        death_cause = chosen
                    raw = (chosen.parameters or {}).get("death_message", f"{pooch.name} died of {chosen.name}.")
                    death_message = substitute_placeholders(raw, {"pooch": pooch})

            for server in await list_servers_for_pooch(pooch.id):
                deaths_by_server.setdefault(server.discord_id, []).append(
                    DeathEvent(
                        server=(await to_server(server)),
                        pooch=(await to_pooch(pooch)),
                        message=death_message,
                    )
                )

            # on_death_triggers (kill/spread/spread_all/send_to_hell/injure)
            for pooch_mutation in pooch_mutations:
                triggers = (pooch_mutation.parameters or {}).get("on_death_triggers", []) or []
                for trigger in triggers:
                    on_death = (trigger.get("on_death") or "none").lower()
                    always = bool(trigger.get("always_on_death", False))
                    chance_v = float(trigger.get("on_death_chance", 1.0))
                    if (
                        on_death == "none"
                        or (not always and (death_cause is None or pooch_mutation.id != death_cause.id))
                        or rng.random() > chance_v
                    ):
                        continue
                    targets_mode = (trigger.get("on_death_targets") or "none").lower()
                    target_pooches: list["Pooch"] = []
                    if targets_mode in ("all", "random") and pooch_kennel_before_death is not None:
                        kennel_pooches = [
                            kp
                            for kp in (await list_pooches_for_kennel(pooch_kennel_before_death.id))
                            if kp.alive and kp.id != pooch.id
                        ]
                        target_pooches = (
                            kennel_pooches
                            if targets_mode == "all"
                            else ([rng.choice(kennel_pooches)] if kennel_pooches else [])
                        )

                    if on_death == "kill":
                        for target in target_pooches:
                            await _kill_pooch(target)
                            impact_msg = substitute_placeholders(
                                trigger.get(
                                    "impact_message",
                                    f"{target.name} died from {pooch.name}'s {pooch_mutation.name}.",
                                ),
                                {"pooch": pooch, "victim": target},
                            )
                            for server in await list_servers_for_pooch(target.id):
                                deaths_by_server.setdefault(server.discord_id, []).append(
                                    DeathEvent(
                                        server=(await to_server(server)),
                                        pooch=(await to_pooch(target)),
                                        message=impact_msg,
                                    )
                                )
                    elif on_death == "spread":
                        for target in target_pooches:
                            await add_mutation_to_pooch(target.id, pooch_mutation.id)
                            target = await get_pooch_by_id(target.id)
                            impact_msg = substitute_placeholders(
                                trigger.get(
                                    "impact_message",
                                    f"{pooch.name} spread its {pooch_mutation.name} to {target.name} as they died.",
                                ),
                                {"pooch": pooch, "victim": target},
                            )
                            for server in await list_servers_for_pooch(target.id):
                                other_events_by_server.setdefault(server.discord_id, []).append(
                                    OtherEvent(
                                        server=(await to_server(server)),
                                        pooch=(await to_pooch(target)),
                                        message=impact_msg,
                                    )
                                )
                    elif on_death == "spread_all":
                        for target in target_pooches:
                            for m in pooch_mutations:
                                await add_mutation_to_pooch(target.id, m.id)
                            target = await get_pooch_by_id(target.id)
                            impact_msg = substitute_placeholders(
                                trigger.get(
                                    "impact_message",
                                    (
                                        f"{pooch.name} spread ALL its mutations to {target.name} as they died, "
                                        f"because of its {pooch_mutation.name}."
                                    ),
                                ),
                                {"pooch": pooch, "victim": target},
                            )
                            for server in await list_servers_for_pooch(target.id):
                                other_events_by_server.setdefault(server.discord_id, []).append(
                                    OtherEvent(
                                        server=(await to_server(server)),
                                        pooch=(await to_pooch(target)),
                                        message=impact_msg,
                                    )
                                )
                    elif on_death == "send_to_hell":
                        await damn_pooch(pooch.id)
                    elif on_death == "injure":
                        # New on_death effect (Section 5A).
                        await apply_on_death_injure(
                            trigger=trigger,
                            source_pooch=pooch,
                            target_pooches=target_pooches,
                            other_events_by_server=other_events_by_server,
                            rng=rng,
                        )

            # Drop body parts to owner on violent death.
            if pooch.owner_discord_id is not None:
                await drop_body_parts(pooch.owner_discord_id, pooch, rng, scale=0.6)

    # 10. Build per-server summaries (only servers with any events are returned).
    out: dict[int, HourChangeSummary] = {}
    all_servers = await list_servers()
    server_by_id = {s.discord_id: s for s in all_servers}
    touched_ids = set(births_by_server) | set(deaths_by_server) | set(other_events_by_server)
    for sid in touched_ids:
        server = server_by_id.get(sid)
        if server is None:
            continue
        out[sid] = HourChangeSummary(
            server=(await to_server(server)),
            hour=current_hour,
            births=births_by_server.get(sid, []),
            deaths=deaths_by_server.get(sid, []),
            other_events=other_events_by_server.get(sid, []),
        )
    return out
