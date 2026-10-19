from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_disease_immunity_to_pooch,
    add_disease_to_pooch,
    consume_owner_item,
    create_pooch_snapshot,
    get_current_day,
    get_item_by_name,
    get_kennel_by_id,
    get_owner_by_discord_id,
    get_pooch_by_id,
    get_pooch_disease_instance,
    give_money_to_owner,
    list_all_diseases,
    list_invisible_pooch_disease_instances,
    list_kennels_for_owner,
    list_owners,
    list_pooch_disease_immunities,
    list_pooch_disease_instances,
    list_pooch_diseases,
    list_pooch_mutations,
    list_pooches_for_kennel,
    modify_pooch_base_health,
    remove_disease_from_pooch,
    reveal_pooch_disease,
    set_owner_hand_cleaned_today,
    treat_pooch_disease,
    update_kennel_messiness,
)
from src.database.models import SNAPSHOT_VET_DISEASES, PoochDisease
from src.logger import get_logger

from .manage_stats import get_effective_stat
from .utils.obfuscation import messiness_label

if TYPE_CHECKING:
    from src.database.models import Disease

logger = get_logger("game/manage_diseases")

DISEASE_BASE_CONTRACTION_CHANCE = 0.005
MESSINESS_CONTRACTION_MULT = 0.002
CONSTITUTION_RESISTANCE_DIVISOR = 100
TREATMENT_RECOVERY_BONUS = 0.15
VET_DIAGNOSE_DISEASES_COST = 30
VET_DISEASE_TREATMENT_BASE_COST = 15
VET_DISEASE_TREATMENT_SEVERITY_MULT = 5
MUTATION_PREDISPOSITION_MULT = 3.0
# How much of a disease's contagion carries from a sick pooch to each kennel mate per hour.
# 0.1 scales it like environmental contraction (Kennel Cough ≈3%/h per sick mate);
# 1.0 uses the full contagion (Kennel Cough ≈32%/h per sick mate: whole kennels fall ill together).
DISEASE_SPREAD_CONTAGION_MULT = 0.1

# Hourly mess accumulation: each pooch contributes mess_output / 72 per hour
# (so a pooch with mess_output 3 adds ~1 mess unit per 24-hour day, and a full kennel
# reaches "Disgusting" in about 2 days).
MESS_PER_POOCH_PER_HOUR_DIVISOR = 72
# Hourly compounding rate: 5% per day scaled to per-hour (~0.208%),
# applied on top of linear accumulation.
MESS_HOURLY_COMPOUND_RATE = 0.05 / 24


def _random_round(amount: float, rng: random.Random) -> int:
    """Round down, then add 1 with chance equal to the fraction, so fractions add up over many hours."""
    whole = int(amount)
    return whole + (1 if rng.random() < amount - whole else 0)


async def get_pooch_disease_instances(pooch_id: int) -> list[PoochDisease]:
    return await list_pooch_disease_instances(pooch_id)


def get_diagnose_diseases_cost() -> int:
    return VET_DIAGNOSE_DISEASES_COST


def get_disease_treatment_cost() -> int:
    return VET_DISEASE_TREATMENT_BASE_COST


def get_public_disease_label(pd: PoochDisease) -> str:
    if pd.visible:
        return pd.disease.name
    return pd.displayed_symptom or "a mysterious illness"


HAND_CLEAN_MESS_REDUCTION = 3


async def clean_kennel_by_hand(owner_discord_id: int, kennel_id: int) -> tuple[bool, str]:
    """
    Free, once-per-day small clean. Uses the owner's ``hand_cleaned_today``
    flag so each owner can only do this once per game day.
    """
    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        return False, "Kennel not found."
    if kennel.owner_discord_id != owner_discord_id:
        return False, "That's not your kennel."
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found."
    if getattr(owner, "hand_cleaned_today", False):
        return False, "You've already hand-cleaned a kennel today."

    new_mess = await update_kennel_messiness(kennel_id, -HAND_CLEAN_MESS_REDUCTION)
    await set_owner_hand_cleaned_today(owner_discord_id, True)
    label = messiness_label(new_mess, capacity=kennel.pooch_limit)
    return True, f"You tidied up — the kennel feels a little cleaner. It is now **{label}**."


async def clean_kennel_with_item(owner_discord_id: int, kennel_id: int, item_name: str) -> tuple[bool, str]:
    """
    Consume one of the owner's cleaning items and apply its ``mess_reduction``
    effect to the kennel. Returns (success, message).
    """
    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        return False, "Kennel not found."
    if kennel.owner_discord_id != owner_discord_id:
        return False, "That's not your kennel."

    item = await get_item_by_name(item_name)
    if item is None:
        return False, f"Unknown item: {item_name}."
    if item.category != "cleaning":
        return False, f"{item.name} is not a cleaning product."

    parameters = item.parameters or {}
    reduction = int(parameters.get("mess_reduction", 0))
    if reduction <= 0:
        return False, f"{item.name} has no cleaning effect."

    ok = await consume_owner_item(owner_discord_id, item.name, 1)
    if not ok:
        return False, f"You don't own any {item.name}."

    new_mess = await update_kennel_messiness(kennel_id, -reduction)
    label = messiness_label(new_mess, capacity=kennel.pooch_limit)
    message = f"You used one {item.name}. The kennel is noticeably cleaner. It is now **{label}**."

    # Harsh products (e.g. bleach) permanently hurt every pooch in the kennel
    side_effect_health = int(parameters.get("side_effect_health", 0))
    if side_effect_health:
        for pooch in await list_pooches_for_kennel(kennel_id):
            if pooch.alive:
                await modify_pooch_base_health(pooch.id, side_effect_health)
        message += " The harsh fumes left your pooches a little worse for wear."
    return True, message


async def _get_mutation_disease_info(pooch_id: int) -> tuple[set[str], set[str]]:
    mutations = await list_pooch_mutations(pooch_id)
    predisposed: set[str] = set()
    immune: set[str] = set()
    for mutation in mutations:
        params = mutation.parameters or {}
        predisposed.update(params.get("disease_predispositions", []))
        immune.update(params.get("disease_immunities", []))
    return predisposed, immune


async def try_contract_disease(
    pooch_id: int,
    disease: Disease,
    constitution: int,
    messiness: int,
    season: str,
    rng: random.Random,
    current_day: int,
    predisposed_names: set[str],
    immune_names: set[str],
    immunity_disease_ids: set[int],
    existing_disease_ids: set[int],
) -> bool:
    if disease.sexually_transmitted or disease.id in existing_disease_ids or disease.id in immunity_disease_ids:
        return False
    if disease.name in immune_names:
        return False
    if disease.seasons and season not in disease.seasons:
        return False

    effective_contagion = disease.contagion_chance
    if disease.season_contagion_modifiers:
        effective_contagion *= disease.season_contagion_modifiers.get(season, 1.0)

    chance = DISEASE_BASE_CONTRACTION_CHANCE + effective_contagion * 0.1 + messiness * MESSINESS_CONTRACTION_MULT
    if constitution > 0:
        chance *= max(0.1, 1.0 - constitution / CONSTITUTION_RESISTANCE_DIVISOR)
    if disease.name in predisposed_names:
        chance *= MUTATION_PREDISPOSITION_MULT
    chance = min(chance, 1.0)

    if rng.random() < chance:
        await add_disease_to_pooch(pooch_id, disease.id, current_day=current_day, rng=rng)
        return True
    return False


async def try_spread_disease(
    source_pooch_id: int,
    target_pooch_id: int,
    disease: Disease,
    target_constitution: int,
    messiness: int,
    season: str,
    rng: random.Random,
    current_day: int,
    target_predisposed_names: Optional[set[str]] = None,
    target_immune_names: Optional[set[str]] = None,
    target_immunity_disease_ids: Optional[set[int]] = None,
    target_existing_disease_ids: Optional[set[int]] = None,
) -> bool:
    del source_pooch_id
    target_predisposed_names = target_predisposed_names or set()
    target_immune_names = target_immune_names or set()
    target_immunity_disease_ids = target_immunity_disease_ids or set()
    target_existing_disease_ids = target_existing_disease_ids or set()

    if (
        disease.sexually_transmitted
        or disease.id in target_existing_disease_ids
        or disease.id in target_immunity_disease_ids
    ):
        return False
    if disease.name in target_immune_names:
        return False
    if disease.seasons and season not in disease.seasons:
        return False

    effective_contagion = disease.contagion_chance
    if disease.season_contagion_modifiers:
        effective_contagion *= disease.season_contagion_modifiers.get(season, 1.0)
    chance = effective_contagion * DISEASE_SPREAD_CONTAGION_MULT + messiness * MESSINESS_CONTRACTION_MULT
    if target_constitution > 0:
        chance *= max(0.1, 1.0 - target_constitution / CONSTITUTION_RESISTANCE_DIVISOR)
    if disease.name in target_predisposed_names:
        chance *= MUTATION_PREDISPOSITION_MULT
    chance = min(chance, 1.0)

    if rng.random() < chance:
        await add_disease_to_pooch(target_pooch_id, disease.id, current_day=current_day, rng=rng)
        return True
    return False


async def try_breed_spread_disease(
    parent_pooch_id: int,
    partner_pooch_id: int,
    disease: Disease,
    partner_constitution: int,
    season: str,
    rng: random.Random,
    current_day: int,
    partner_predisposed_names: Optional[set[str]] = None,
    partner_immune_names: Optional[set[str]] = None,
    partner_immunity_disease_ids: Optional[set[int]] = None,
    partner_existing_disease_ids: Optional[set[int]] = None,
) -> bool:
    del parent_pooch_id
    partner_predisposed_names = partner_predisposed_names or set()
    partner_immune_names = partner_immune_names or set()
    partner_immunity_disease_ids = partner_immunity_disease_ids or set()
    partner_existing_disease_ids = partner_existing_disease_ids or set()

    if disease.id in partner_existing_disease_ids or disease.id in partner_immunity_disease_ids:
        return False
    if disease.name in partner_immune_names:
        return False
    if disease.seasons and season not in disease.seasons:
        return False

    chance = disease.contagion_chance
    if disease.season_contagion_modifiers:
        chance *= disease.season_contagion_modifiers.get(season, 1.0)
    if partner_constitution > 0:
        chance *= max(0.1, 1.0 - partner_constitution / CONSTITUTION_RESISTANCE_DIVISOR)
    if disease.name in partner_predisposed_names:
        chance *= MUTATION_PREDISPOSITION_MULT
    chance = min(chance, 1.0)

    if rng.random() < chance:
        await add_disease_to_pooch(partner_pooch_id, disease.id, current_day=current_day, rng=rng)
        return True
    return False


async def try_inherit_disease(parent_disease: Disease, puppy_id: int, rng: random.Random, current_day: int) -> bool:
    if parent_disease.heritability <= 0:
        return False
    if rng.random() < parent_disease.heritability:
        await add_disease_to_pooch(puppy_id, parent_disease.id, current_day=current_day, rng=rng)
        return True
    return False


async def try_recover_from_disease(pooch_disease: PoochDisease, current_day: int, rng: random.Random) -> bool:
    disease = pooch_disease.disease
    if not disease.curable:
        return False
    recovery_chance = disease.recovery_chance
    if recovery_chance <= 0 and not pooch_disease.treated:
        return False
    if pooch_disease.treated:
        recovery_chance += TREATMENT_RECOVERY_BONUS
    recovery_chance = min(recovery_chance, 1.0)
    if rng.random() < recovery_chance:
        await remove_disease_from_pooch(pooch_disease.pooch_id, disease.id)
        if disease.immunity_duration is not None and disease.immunity_duration > 0:
            await add_disease_immunity_to_pooch(
                pooch_disease.pooch_id, disease.id, current_day + disease.immunity_duration
            )
        return True
    return False


async def diagnose_diseases(
    owner_discord_id: int,
    pooch_id: int,
    rng_seed: Optional[int] = None,
) -> tuple[bool, str, list[str]]:
    import random as _random

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", []
    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return False, "Pooch not found.", []
    if pooch.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", []
    if owner.dollars < VET_DIAGNOSE_DISEASES_COST:
        return False, f"Not enough money. Diagnosis costs **${VET_DIAGNOSE_DISEASES_COST}**.", []

    rng_inst = _random.Random(rng_seed)
    invisible_instances = await list_invisible_pooch_disease_instances(pooch_id)

    await give_money_to_owner(owner_discord_id, -VET_DIAGNOSE_DISEASES_COST)
    revealed: list[str] = []
    for pd in invisible_instances:
        if rng_inst.random() < float(getattr(pd.disease, "reveal_chance", 1.0)):
            await reveal_pooch_disease(pd.id)
            revealed.append(pd.disease.name)

    # Snapshot: record every disease known after the diagnosis, like injury/mutation diagnoses do
    known_disease_ids = [pd.disease_id for pd in await list_pooch_disease_instances(pooch_id) if pd.visible]
    await create_pooch_snapshot(
        pooch_id=pooch_id,
        kind=SNAPSHOT_VET_DISEASES,
        description=f"{pooch.name} had their diseases examined by a vet.",
        entity_ids=known_disease_ids or None,
    )
    return True, "", revealed


async def treat_disease(owner_discord_id: int, pooch_disease_id: int) -> tuple[bool, str, int]:
    pd = await get_pooch_disease_instance(pooch_disease_id)
    if pd is None:
        return False, "Disease not found.", 0
    disease = pd.disease

    if pd.pooch.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", 0
    if pd.treated:
        return False, "This disease has already been treated.", 0
    if not disease.treatable:
        return False, "This disease cannot be treated.", 0
    if not disease.curable:
        return False, "This disease cannot be cured with treatment.", 0

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", 0
    cost = VET_DISEASE_TREATMENT_BASE_COST
    if owner.dollars < cost:
        return False, f"Not enough money. Treatment costs **${cost}**.", 0

    await give_money_to_owner(owner_discord_id, -cost)
    await treat_pooch_disease(pooch_disease_id)
    return True, f"Treatment successful. Charged **${cost}**.", cost


async def handle_breeding_diseases(
    father_id: int,
    mother_id: int,
    puppy_ids: list[int],
    season: str,
    rng: random.Random,
) -> list[tuple[int, str, str]]:
    current_day = await get_current_day()
    breed_events: list[tuple[int, str, str]] = []
    father_diseases = await list_pooch_disease_instances(father_id)
    mother_diseases = await list_pooch_disease_instances(mother_id)

    for parent_id, parent_diseases, partner_id in [
        (father_id, father_diseases, mother_id),
        (mother_id, mother_diseases, father_id),
    ]:
        partner_existing = {d.id for d in (await list_pooch_diseases(partner_id))}
        partner_immunities = {imm.disease_id for imm in (await list_pooch_disease_immunities(partner_id))}
        partner_predisposed, partner_immune_names = await _get_mutation_disease_info(partner_id)
        partner_constitution = (await get_effective_stat(partner_id, "constitution")) or 10

        for pd_instance in parent_diseases:
            if await try_breed_spread_disease(
                parent_pooch_id=parent_id,
                partner_pooch_id=partner_id,
                disease=pd_instance.disease,
                partner_constitution=partner_constitution,
                season=season,
                rng=rng,
                current_day=current_day,
                partner_predisposed_names=partner_predisposed,
                partner_immune_names=partner_immune_names,
                partner_immunity_disease_ids=partner_immunities,
                partner_existing_disease_ids=partner_existing,
            ):
                partner_instance = next(
                    (
                        pd
                        for pd in await list_pooch_disease_instances(partner_id)
                        if pd.disease_id == pd_instance.disease_id
                    ),
                    None,
                )
                public_label = (
                    get_public_disease_label(partner_instance) if partner_instance else pd_instance.disease.name
                )
                breed_events.append((partner_id, public_label, "spread"))

    seen_disease_ids: set[int] = set()
    for pd_instance in father_diseases + mother_diseases:
        if pd_instance.disease_id in seen_disease_ids:
            continue
        seen_disease_ids.add(pd_instance.disease_id)
        for puppy_id in puppy_ids:
            if await try_inherit_disease(pd_instance.disease, puppy_id, rng, current_day):
                puppy_instance = next(
                    (
                        pd
                        for pd in await list_pooch_disease_instances(puppy_id)
                        if pd.disease_id == pd_instance.disease_id
                    ),
                    None,
                )
                public_label = get_public_disease_label(puppy_instance) if puppy_instance else pd_instance.disease.name
                breed_events.append((puppy_id, public_label, "inherited"))

    return breed_events


# ---------------------------------------------------------------------------
# Hourly disease tick
# ---------------------------------------------------------------------------


async def run_hourly_disease_tick(season: str, rng_seed: Optional[int] = None) -> dict[int, list[tuple[int, str, str]]]:
    """
    Run the disease model for one hour of game time.

    Contraction and recovery chances from ``try_contract_disease`` /
    ``try_recover_from_disease`` are used directly — those functions hold
    the authoritative per-roll probability, and the hourly loop fires them
    once per hour with no additional scaling.

    Mess accumulates linearly each hour (pooch.mess_output /
    MESS_PER_POOCH_PER_HOUR_DIVISOR) and also compounds at
    MESS_HOURLY_COMPOUND_RATE (≈0.208%/hour, equivalent to 5%/day). Both are
    rounded randomly, so their fractions add up correctly over many hours.

    Pooches that were sick when the hour began can also pass their diseases to
    kennel mates (``try_spread_disease``, scaled by DISEASE_SPREAD_CONTAGION_MULT).

    Strays use a fixed environmental messiness in place of a kennel value, and roll
    to recover like kennel pooches.
    """
    from src.database import list_servers, list_strays_for_server

    from .constants import STRAY_ENVIRONMENTAL_MESSINESS

    rng = random.Random(rng_seed)
    current_day = await get_current_day()

    all_diseases = await list_all_diseases(season=season)
    kennel_diseases = [d for d in all_diseases if not d.sexually_transmitted]
    events: dict[int, list[tuple[int, str, str]]] = {}

    # 1. Kennel path.
    for owner in await list_owners():
        for kennel in await list_kennels_for_owner(owner.discord_id):
            pooches = [p for p in (await list_pooches_for_kennel(kennel.id)) if p.alive]
            if not pooches:
                continue

            # Linear mess accumulation (per-pooch per hour). Rounded randomly: a fixed rounding would lose
            # (or gain) the same fraction every hour, so a one-dog kennel would never get messy.
            linear_add = _random_round(
                sum(int(getattr(p, "mess_output", 2) or 2) for p in pooches) / MESS_PER_POOCH_PER_HOUR_DIVISOR, rng
            )
            if linear_add > 0:
                await update_kennel_messiness(kennel.id, linear_add)

            # Compound mess growth (~0.208%/hour → ~5%/day).
            current_mess = kennel.messiness + linear_add
            compound_add = _random_round(current_mess * MESS_HOURLY_COMPOUND_RATE, rng)
            if compound_add > 0:
                await update_kennel_messiness(kennel.id, compound_add)
                current_mess += compound_add

            messiness = current_mess

            predisposed_cache: dict[int, set[str]] = {}
            immune_names_cache: dict[int, set[str]] = {}
            existing_cache: dict[int, set[int]] = {}
            immunity_cache: dict[int, set[int]] = {}
            const_cache: dict[int, int] = {}
            # What each pooch was sick with when the hour began: only these spread to kennel mates this hour.
            carried_cache: dict[int, list] = {}

            for p in pooches:
                pre, imm = await _get_mutation_disease_info(p.id)
                predisposed_cache[p.id] = pre
                immune_names_cache[p.id] = imm
                carried_cache[p.id] = list(await list_pooch_diseases(p.id))
                existing_cache[p.id] = {d.id for d in carried_cache[p.id]}
                immunity_cache[p.id] = {im.disease_id for im in (await list_pooch_disease_immunities(p.id))}
                const_cache[p.id] = (await get_effective_stat(p.id, "constitution")) or p.constitution

            for p in pooches:
                contracted_now: set[int] = set()
                for disease in kennel_diseases:
                    if disease.id in existing_cache.get(p.id, set()):
                        continue
                    if await try_contract_disease(
                        pooch_id=p.id,
                        disease=disease,
                        constitution=const_cache.get(p.id, p.constitution),
                        messiness=messiness,
                        season=season,
                        rng=rng,
                        current_day=current_day,
                        predisposed_names=predisposed_cache.get(p.id, set()),
                        immune_names=immune_names_cache.get(p.id, set()),
                        immunity_disease_ids=immunity_cache.get(p.id, set()),
                        existing_disease_ids=existing_cache.get(p.id, set()),
                    ):
                        existing_cache.setdefault(p.id, set()).add(disease.id)
                        contracted_now.add(disease.id)
                        events.setdefault(p.id, []).append((disease.id, disease.name, "contracted"))

                for source in pooches:
                    if source.id == p.id:
                        continue
                    for disease in carried_cache.get(source.id, []):
                        if await try_spread_disease(
                            source_pooch_id=source.id,
                            target_pooch_id=p.id,
                            disease=disease,
                            target_constitution=const_cache.get(p.id, p.constitution),
                            messiness=messiness,
                            season=season,
                            rng=rng,
                            current_day=current_day,
                            target_predisposed_names=predisposed_cache.get(p.id, set()),
                            target_immune_names=immune_names_cache.get(p.id, set()),
                            target_immunity_disease_ids=immunity_cache.get(p.id, set()),
                            target_existing_disease_ids=existing_cache.get(p.id, set()),
                        ):
                            existing_cache.setdefault(p.id, set()).add(disease.id)
                            contracted_now.add(disease.id)
                            events.setdefault(p.id, []).append((disease.id, disease.name, "spread"))

                for pd_instance in await list_pooch_disease_instances(p.id):
                    # A disease caught this hour can't also be shaken off this hour.
                    if pd_instance.disease_id in contracted_now:
                        continue
                    if await try_recover_from_disease(pd_instance, current_day=current_day, rng=rng):
                        events.setdefault(p.id, []).append(
                            (pd_instance.disease_id, pd_instance.disease.name, "recovered")
                        )

    # 2. Stray path — use fixed environmental messiness (medium-dirty kennel equivalent).
    for server in await list_servers():
        strays = await list_strays_for_server(server.discord_id)
        for p in strays:
            if not p.alive:
                continue
            pre, imm = await _get_mutation_disease_info(p.id)
            existing = {d.id for d in (await list_pooch_diseases(p.id))}
            immunity = {im.disease_id for im in (await list_pooch_disease_immunities(p.id))}
            const = (await get_effective_stat(p.id, "constitution")) or p.constitution
            contracted_now: set[int] = set()
            for disease in kennel_diseases:
                if disease.id in existing:
                    continue
                if await try_contract_disease(
                    pooch_id=p.id,
                    disease=disease,
                    constitution=const,
                    messiness=STRAY_ENVIRONMENTAL_MESSINESS,
                    season=season,
                    rng=rng,
                    current_day=current_day,
                    predisposed_names=pre,
                    immune_names=imm,
                    immunity_disease_ids=immunity,
                    existing_disease_ids=existing,
                ):
                    existing.add(disease.id)
                    contracted_now.add(disease.id)
                    events.setdefault(p.id, []).append((disease.id, disease.name, "contracted"))

            for pd_instance in await list_pooch_disease_instances(p.id):
                if pd_instance.disease_id in contracted_now:
                    continue
                if await try_recover_from_disease(pd_instance, current_day=current_day, rng=rng):
                    events.setdefault(p.id, []).append((pd_instance.disease_id, pd_instance.disease.name, "recovered"))

    return events
