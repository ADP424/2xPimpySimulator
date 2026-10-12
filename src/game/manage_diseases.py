from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_disease_immunity_to_pooch,
    add_disease_to_pooch,
    get_current_day,
    get_kennel_by_id,
    get_owner_by_discord_id,
    get_pooch_by_id,
    get_pooch_constitution,
    get_pooch_disease_instance,
    give_money_to_owner,
    list_all_diseases,
    list_kennels_for_owner,
    list_owners,
    list_pooch_disease_immunities,
    list_pooch_disease_instances,
    list_pooch_diseases,
    list_pooch_mutations,
    list_pooches_for_kennel,
    remove_disease_from_pooch,
    remove_expired_disease_immunities,
    reveal_pooch_disease,
    set_kennel_messiness,
    treat_pooch_disease,
    update_kennel_messiness,
)
from src.database.models import PoochDisease
from src.logger import get_logger

if TYPE_CHECKING:
    from src.database.models import Disease

logger = get_logger("game/manage_diseases")

DISEASE_BASE_CONTRACTION_CHANCE = 0.005
MESSINESS_CONTRACTION_MULT = 0.005
CONSTITUTION_RESISTANCE_DIVISOR = 100
MESS_PER_POOCH_PER_DAY = 2
MESS_COMPOUND_RATE = 0.1
TREATMENT_RECOVERY_BONUS = 0.15
VET_DIAGNOSE_DISEASES_COST = 30
VET_DISEASE_TREATMENT_BASE_COST = 15
VET_DISEASE_TREATMENT_SEVERITY_MULT = 5
MUTATION_PREDISPOSITION_MULT = 3.0


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


async def accumulate_kennel_mess(kennel_id: int, num_pooches: int) -> int:
    return await update_kennel_messiness(kennel_id, MESS_PER_POOCH_PER_DAY * num_pooches)


async def compound_kennel_mess(kennel_id: int, current_messiness: int) -> int:
    growth = int(current_messiness * MESS_COMPOUND_RATE)
    if growth > 0:
        return await update_kennel_messiness(kennel_id, growth)
    return current_messiness


async def clean_kennel(owner_discord_id: int, kennel_id: int) -> tuple[bool, str]:
    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        return False, "Kennel not found."
    if kennel.owner_discord_id != owner_discord_id:
        return False, "That's not your kennel."
    await set_kennel_messiness(kennel_id, 0)
    return True, "Kennel cleaned!"


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
    chance = effective_contagion + messiness * MESSINESS_CONTRACTION_MULT
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
    invisible_instances = [pd for pd in await list_pooch_disease_instances(pooch_id) if not pd.visible]

    await give_money_to_owner(owner_discord_id, -VET_DIAGNOSE_DISEASES_COST)
    revealed: list[str] = []
    for pd in invisible_instances:
        if rng_inst.random() < float(getattr(pd.disease, "reveal_chance", 1.0)):
            await reveal_pooch_disease(pd.id)
            revealed.append(pd.disease.name)
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


async def run_daily_disease_tick(season: str, rng_seed: Optional[int] = None) -> dict[int, list[tuple[int, str, str]]]:
    rng = random.Random(rng_seed)
    current_day = await get_current_day()
    await remove_expired_disease_immunities(current_day)

    all_diseases = await list_all_diseases(season=season)
    kennel_diseases = [d for d in all_diseases if not d.sexually_transmitted]
    events: dict[int, list[tuple[int, str, str]]] = {}

    for owner in await list_owners():
        for kennel in await list_kennels_for_owner(owner.discord_id):
            pooches = await list_pooches_for_kennel(kennel.id)
            living_pooches = [p for p in pooches if p.alive]
            if not living_pooches:
                continue

            messiness = await accumulate_kennel_mess(kennel.id, len(living_pooches))
            messiness = await compound_kennel_mess(kennel.id, messiness)

            pooch_diseases_cache: dict[int, set[int]] = {}
            pooch_immunity_cache: dict[int, set[int]] = {}
            pooch_predisposed_cache: dict[int, set[str]] = {}
            pooch_immune_names_cache: dict[int, set[str]] = {}
            pooch_constitution_cache: dict[int, int] = {}

            for pooch in living_pooches:
                pooch_diseases_cache[pooch.id] = {d.id for d in (await list_pooch_diseases(pooch.id))}
                pooch_immunity_cache[pooch.id] = {
                    imm.disease_id for imm in (await list_pooch_disease_immunities(pooch.id))
                }
                predisposed, immune_names = await _get_mutation_disease_info(pooch.id)
                pooch_predisposed_cache[pooch.id] = predisposed
                pooch_immune_names_cache[pooch.id] = immune_names
                pooch_constitution_cache[pooch.id] = (await get_pooch_constitution(pooch.id)) or pooch.constitution

            for pooch in living_pooches:
                for pd_instance in await list_pooch_disease_instances(pooch.id):
                    disease = pd_instance.disease
                    if disease.sexually_transmitted or disease.contagion_chance <= 0:
                        continue
                    for target in living_pooches:
                        if target.id == pooch.id:
                            continue
                        spread = await try_spread_disease(
                            source_pooch_id=pooch.id,
                            target_pooch_id=target.id,
                            disease=disease,
                            target_constitution=pooch_constitution_cache.get(target.id, target.constitution),
                            messiness=messiness,
                            season=season,
                            rng=rng,
                            current_day=current_day,
                            target_predisposed_names=pooch_predisposed_cache.get(target.id, set()),
                            target_immune_names=pooch_immune_names_cache.get(target.id, set()),
                            target_immunity_disease_ids=pooch_immunity_cache.get(target.id, set()),
                            target_existing_disease_ids=pooch_diseases_cache.get(target.id, set()),
                        )
                        if spread:
                            pooch_diseases_cache.setdefault(target.id, set()).add(disease.id)
                            target_instance = next(
                                (
                                    pd
                                    for pd in await list_pooch_disease_instances(target.id)
                                    if pd.disease_id == disease.id
                                ),
                                None,
                            )
                            public_label = (
                                get_public_disease_label(target_instance) if target_instance else disease.name
                            )
                            events.setdefault(target.id, []).append((disease.id, public_label, "spread"))

            for pooch in living_pooches:
                for disease in kennel_diseases:
                    contracted = await try_contract_disease(
                        pooch_id=pooch.id,
                        disease=disease,
                        constitution=pooch_constitution_cache.get(pooch.id, pooch.constitution),
                        messiness=messiness,
                        season=season,
                        rng=rng,
                        current_day=current_day,
                        predisposed_names=pooch_predisposed_cache.get(pooch.id, set()),
                        immune_names=pooch_immune_names_cache.get(pooch.id, set()),
                        immunity_disease_ids=pooch_immunity_cache.get(pooch.id, set()),
                        existing_disease_ids=pooch_diseases_cache.get(pooch.id, set()),
                    )
                    if contracted:
                        pooch_diseases_cache.setdefault(pooch.id, set()).add(disease.id)
                        pooch_instance = next(
                            (pd for pd in await list_pooch_disease_instances(pooch.id) if pd.disease_id == disease.id),
                            None,
                        )
                        public_label = get_public_disease_label(pooch_instance) if pooch_instance else disease.name
                        events.setdefault(pooch.id, []).append((disease.id, public_label, "contracted"))

            for pooch in living_pooches:
                for pd_instance in await list_pooch_disease_instances(pooch.id):
                    if await try_recover_from_disease(pd_instance, current_day=current_day, rng=rng):
                        pooch_diseases_cache.get(pooch.id, set()).discard(pd_instance.disease_id)
                        public_label = pd_instance.disease.name if pd_instance.visible else "a mysterious illness"
                        events.setdefault(pooch.id, []).append((pd_instance.disease_id, public_label, "recovered"))

    return events


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
        partner_constitution = (await get_pooch_constitution(partner_id)) or 10

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
