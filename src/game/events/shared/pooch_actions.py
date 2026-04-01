from __future__ import annotations

import logging
import random
from typing import Any, Optional

from src.database import (
    add_breed_to_pooch,
    add_injury_to_pooch,
    add_mutation_to_pooch,
    bury_pooch,
    damn_pooch,
    get_breed_by_name,
    get_injury_by_name,
    get_mutation_by_name,
    get_pooch_by_id,
    get_random_injury,
    modify_pooch_age,
    modify_pooch_aggressiveness,
    modify_pooch_base_health,
    modify_pooch_breeding_cooldown,
    modify_pooch_constitution,
    modify_pooch_cuteness,
    modify_pooch_dexterity,
    modify_pooch_fertility,
    modify_pooch_fluffiness,
    modify_pooch_intelligence,
    modify_pooch_strength,
    remove_breed_from_pooch,
    remove_mutation_from_pooch,
    remove_pooch_from_kennel,
    remove_random_breed_from_pooch,
    remove_random_mutation_from_pooch,
    rename_pooch,
    reset_pooch_breeding_cooldown,
    set_pooch_age,
    set_pooch_aggressiveness,
    set_pooch_base_health,
    set_pooch_breeding_cooldown,
    set_pooch_constitution,
    set_pooch_cuteness,
    set_pooch_dead,
    set_pooch_dexterity,
    set_pooch_fertility,
    set_pooch_fluffiness,
    set_pooch_intelligence,
    set_pooch_strength,
)
from src.game.constants import (
    FIGHT_ATTACK_AGGRESSIVENESS_WEIGHT,
    FIGHT_ATTACK_DEXTERITY_WEIGHT,
    FIGHT_ATTACK_SIZE_STENGTH_WEIGHT,
    FIGHT_ATTACK_STRENGTH_WEIGHT,
    FIGHT_CONSTITUTION_FATIGUE_REDUCTION,
    FIGHT_DEFENDER_STRENGTH_BONUS,
    FIGHT_DEFENSE_CONSTITUTION_WEIGHT,
    FIGHT_DEFENSE_DEXTERITY_WEIGHT,
    FIGHT_DEFENSE_STRENGTH_WEIGHT,
    FIGHT_INJURY_BITE_CHANCE,
    FIGHT_MODERATE_BITE_DAMAGE_THRESHOLD,
    FIGHT_RANDOM_MULTIPLIER_RANGE,
    FIGHT_ROUNDS,
    FIGHT_SEVERE_BITE_DAMAGE_THRESHOLD,
    FIGHT_STRENGTH_LOSS_PER_ROUND,
)

from .amount import get_amount_from_parameters, get_mode, resolve_amount

logger = logging.getLogger(__name__)

# Default breeding cooldown constant — imported lazily to avoid circular risk
_POOCH_BREEDING_COOLDOWN: Optional[int] = None


def _get_breeding_cooldown_default() -> int:
    global _POOCH_BREEDING_COOLDOWN
    if _POOCH_BREEDING_COOLDOWN is None:
        from src.database.constants import POOCH_BREEDING_COOLDOWN

        _POOCH_BREEDING_COOLDOWN = POOCH_BREEDING_COOLDOWN
    return _POOCH_BREEDING_COOLDOWN


async def handle_modify_health(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle modify_base_health."""
    pre_rolled, roll_once = resolve_amount(parameters, rng)
    mode = get_mode(parameters)
    for pooch_id in pooch_ids:
        amount = pre_rolled if roll_once else get_amount_from_parameters(parameters, rng)
        if mode == "set":
            pooch = await set_pooch_base_health(pooch_id, amount)
        else:
            pooch = await modify_pooch_base_health(pooch_id, amount)
        if pooch:
            result.pooches_affected.append(pooch_id)
            result.extra_data.setdefault("health_changes", {})[pooch_id] = amount


async def handle_modify_age(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle modify_pooch_age."""
    pre_rolled, roll_once = resolve_amount(parameters, rng)
    mode = get_mode(parameters)
    for pooch_id in pooch_ids:
        amount = pre_rolled if roll_once else get_amount_from_parameters(parameters, rng)
        if mode == "set":
            pooch = await set_pooch_age(pooch_id, amount)
        else:
            pooch = await modify_pooch_age(pooch_id, amount)
        if pooch:
            result.pooches_affected.append(pooch_id)
            result.extra_data.setdefault("age_changes", {})[pooch_id] = amount


async def handle_kill_pooch(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle kill_pooch."""
    for pooch_id in pooch_ids:
        pooch = await set_pooch_dead(pooch_id)
        if pooch:
            if pooch.owner_discord_id is not None:
                await remove_pooch_from_kennel(pooch.id)
                await bury_pooch(pooch.owner_discord_id, pooch.id)
            result.pooches_killed.append(pooch_id)
            result.extra_data.setdefault("killed_pooches", []).append({"pooch_id": pooch_id, "pooch_name": pooch.name})
    if result.pooches_killed:
        count = len(result.pooches_killed)
        result.message = "A pooch has died!" if count == 1 else f"{count} pooches have died!"


async def handle_injure_pooch(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle injure_pooch — adds a named or random injury to each target pooch.

    If "injury" is specified, use that injury by name.
    Otherwise pick a random injury, optionally filtered by:
      - min_severity / max_severity: severity range (trivial/minor/moderate/major/critical/remarkable/catastrophic)
      - min_health_impact / max_health_impact: health impact range
    """
    injury_name = parameters.get("injury")

    def _record_injury(pooch_id: int, pooch_name: Optional[str], inj_name: str) -> None:
        result.extra_data.setdefault("injuries_added", []).append(
            {"pooch_id": pooch_id, "pooch_name": pooch_name, "injury_name": inj_name}
        )

    if injury_name:
        injury = await get_injury_by_name(str(injury_name))
        if injury is None:
            logger.warning("injure_pooch: unknown injury %r", injury_name)
            return
        for pooch_id in pooch_ids:
            added = await add_injury_to_pooch(pooch_id, injury.id)
            if added:
                result.pooches_affected.append(pooch_id)
                pooch = await get_pooch_by_id(pooch_id)
                _record_injury(pooch_id, pooch.name if pooch else None, injury.name)
    else:
        min_severity = parameters.get("min_severity")
        max_severity = parameters.get("max_severity")
        min_health_impact = parameters.get("min_health_impact")
        max_health_impact = parameters.get("max_health_impact")
        roll_once = parameters.get("roll_once", False)

        if roll_once:
            injury = await get_random_injury(
                rng,
                min_severity=str(min_severity) if min_severity else None,
                max_severity=str(max_severity) if max_severity else None,
                min_health_impact=str(min_health_impact) if min_health_impact else None,
                max_health_impact=str(max_health_impact) if max_health_impact else None,
            )
            if injury is None:
                return
            for pooch_id in pooch_ids:
                added = await add_injury_to_pooch(pooch_id, injury.id)
                if added:
                    result.pooches_affected.append(pooch_id)
                    pooch = await get_pooch_by_id(pooch_id)
                    _record_injury(pooch_id, pooch.name if pooch else None, injury.name)
        else:
            for pooch_id in pooch_ids:
                injury = await get_random_injury(
                    rng,
                    min_severity=str(min_severity) if min_severity else None,
                    max_severity=str(max_severity) if max_severity else None,
                    min_health_impact=str(min_health_impact) if min_health_impact else None,
                    max_health_impact=str(max_health_impact) if max_health_impact else None,
                )
                if injury is None:
                    continue
                added = await add_injury_to_pooch(pooch_id, injury.id)
                if added:
                    result.pooches_affected.append(pooch_id)
                    pooch = await get_pooch_by_id(pooch_id)
                    _record_injury(pooch_id, pooch.name if pooch else None, injury.name)


async def handle_add_mutation(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle add_mutation by name or random selection."""
    mutation_name = parameters.get("mutation")
    mutation_names = parameters.get("mutations")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    min_health_impact = parameters.get("min_health_impact")
    max_health_impact = parameters.get("max_health_impact")
    for pooch_id in pooch_ids:
        if isinstance(mutation_names, list) and mutation_names:
            for m in mutation_names:
                mut = await get_mutation_by_name(str(m))
                if mut:
                    await add_mutation_to_pooch(pooch_id, mut.id)
        elif mutation_name:
            mut = await get_mutation_by_name(str(mutation_name))
            if mut:
                await add_mutation_to_pooch(pooch_id, mut.id)
        else:
            await add_mutation_to_pooch(
                pooch_id,
                rng=rng,
                min_rarity=min_rarity,
                max_rarity=max_rarity,
                min_health_impact=min_health_impact,
                max_health_impact=max_health_impact,
            )
        result.pooches_affected.append(pooch_id)


async def handle_remove_mutation(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle remove_mutation by name or random selection."""
    mutation_name = parameters.get("mutation")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    min_health_impact = parameters.get("min_health_impact")
    max_health_impact = parameters.get("max_health_impact")
    for pooch_id in pooch_ids:
        if mutation_name:
            mut = await get_mutation_by_name(str(mutation_name))
            if mut:
                removed = await remove_mutation_from_pooch(pooch_id, mut.id)
            else:
                removed = False
        else:
            removed = await remove_random_mutation_from_pooch(
                pooch_id,
                rng=rng,
                min_rarity=min_rarity,
                max_rarity=max_rarity,
                min_health_impact=min_health_impact,
                max_health_impact=max_health_impact,
            )
        if removed:
            result.mutations_removed.append((pooch_id, removed.mutation_id))
            result.pooches_affected.append(pooch_id)


async def handle_add_breed(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle add_breed by name or random selection."""
    breed_name = parameters.get("breed")
    weight = parameters.get("weight", 0.5)
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    for pooch_id in pooch_ids:
        if breed_name:
            breed = await get_breed_by_name(str(breed_name))
            if breed:
                await add_breed_to_pooch(pooch_id, breed.id, weight=weight)
        else:
            await add_breed_to_pooch(
                pooch_id,
                rng=rng,
                weight=weight,
                min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                max_rarity=max_rarity if isinstance(max_rarity, str) else None,
            )
        result.pooches_affected.append(pooch_id)


async def handle_remove_breed(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle remove_breed by name or random selection."""
    breed_name = parameters.get("breed")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    for pooch_id in pooch_ids:
        if breed_name:
            breed = await get_breed_by_name(str(breed_name))
            if breed:
                removed = await remove_breed_from_pooch(pooch_id, breed.id)
            else:
                removed = None
        else:
            removed = await remove_random_breed_from_pooch(
                pooch_id,
                rng=rng,
                min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                max_rarity=max_rarity if isinstance(max_rarity, str) else None,
            )
        if removed:
            result.pooches_affected.append(pooch_id)
            pooch = await get_pooch_by_id(pooch_id)
            breed_name_str = None
            if hasattr(removed, "breed") and removed.breed:
                breed_name_str = removed.breed.name
            result.extra_data.setdefault("breeds_removed", []).append(
                {
                    "pooch_id": pooch_id,
                    "pooch_name": pooch.name if pooch else None,
                    "breed_name": breed_name_str,
                }
            )


async def handle_rename_pooch(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle rename_pooch."""
    new_name = parameters.get("name")
    if new_name:
        for pooch_id in pooch_ids:
            await rename_pooch(pooch_id, str(new_name))
            result.pooches_affected.append(pooch_id)


_MODIFY_FNS = {
    "strength": modify_pooch_strength,
    "cuteness": modify_pooch_cuteness,
    "fluffiness": modify_pooch_fluffiness,
    "intelligence": modify_pooch_intelligence,
    "dexterity": modify_pooch_dexterity,
    "fertility": modify_pooch_fertility,
    "aggressiveness": modify_pooch_aggressiveness,
    "constitution": modify_pooch_constitution,
}

_SET_FNS = {
    "strength": set_pooch_strength,
    "cuteness": set_pooch_cuteness,
    "fluffiness": set_pooch_fluffiness,
    "intelligence": set_pooch_intelligence,
    "dexterity": set_pooch_dexterity,
    "fertility": set_pooch_fertility,
    "aggressiveness": set_pooch_aggressiveness,
    "constitution": set_pooch_constitution,
}


async def handle_modify_stat(
    action_type: str,
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle modify_<stat> for all heritable stats."""
    stat = action_type[len("modify_") :]
    modify_fn = _MODIFY_FNS[stat]
    set_fn = _SET_FNS[stat]
    pre_rolled, roll_once = resolve_amount(parameters, rng)
    mode = get_mode(parameters)
    for pooch_id in pooch_ids:
        amount = pre_rolled if roll_once else get_amount_from_parameters(parameters, rng)
        if mode == "set":
            pooch = await set_fn(pooch_id, amount)
        else:
            pooch = await modify_fn(pooch_id, amount)
        if pooch:
            result.pooches_affected.append(pooch_id)
            result.extra_data.setdefault("stat_changes", []).append(
                {"pooch_id": pooch_id, "pooch_name": pooch.name, "stat": stat, "amount": amount, "mode": mode}
            )


async def handle_damn_pooch(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
    context: Any,
    candidate_ids_attr: str,
) -> None:
    """Handle damn_pooch. Removes damned pooches from the given candidate pool attribute on context."""
    for pooch_id in pooch_ids:
        pooch = await get_pooch_by_id(pooch_id)
        await set_pooch_dead(pooch_id)
        hell_entry = await damn_pooch(pooch_id)
        if hell_entry:
            result.pooches_killed.append(pooch_id)
            result.extra_data.setdefault("killed_pooches", []).append(
                {"pooch_id": pooch_id, "pooch_name": pooch.name if pooch else None}
            )
            save_as = parameters.get("save_as")
            if isinstance(save_as, str) and save_as:
                context.extra_data[save_as] = {"pooch_ids": [pooch_id]}
        candidate_pool = getattr(context, candidate_ids_attr, None)
        if candidate_pool is not None and pooch_id in candidate_pool:
            candidate_pool.remove(pooch_id)


async def handle_modify_breeding_cooldown(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle modify_breeding_cooldown."""
    if parameters.get("reset"):
        for pooch_id in pooch_ids:
            await reset_pooch_breeding_cooldown(pooch_id)
            result.pooches_affected.append(pooch_id)
        return
    mode = get_mode(parameters)
    pre_rolled, roll_once = resolve_amount(parameters, rng)
    for pooch_id in pooch_ids:
        amount = pre_rolled if roll_once else get_amount_from_parameters(parameters, rng)
        if mode == "set":
            await set_pooch_breeding_cooldown(pooch_id, max(0, amount))
        else:
            await modify_pooch_breeding_cooldown(pooch_id, amount)
        result.pooches_affected.append(pooch_id)


async def handle_select_pooch(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle select_pooch — resolves and saves into a named slot; no other side effects."""
    # Resolution and save_as are handled by the resolver before this is called.
    pass


# ---------------------------------------------------------------------------
# Fight mechanics
# ---------------------------------------------------------------------------

_FIGHT_INJURY_SEVERE_BITE = "Severe Bite"
_FIGHT_INJURY_MODERATE_BITE = "Moderate Bite"
_FIGHT_INJURY_MINOR_BITE = "Minor Bite"
_FIGHT_INJURY_SEVERE_SCRATCH = "Severe Scratch"
_FIGHT_INJURY_MODERATE_SCRATCH = "Moderate Scratch"
_FIGHT_INJURY_MINOR_SCRATCH = "Minor Scratch"


def _compute_damage(
    attacker_strength: float,
    attacker_size: int,
    attacker_dexterity: int,
    attacker_aggressiveness: int,
    defender_strength: float,
    defender_dexterity: int,
    defender_constitution: int,
    defender_size: int,
    rng: random.Random,
) -> int:
    """Return integer damage dealt in one round."""
    attack_mult = rng.uniform(*FIGHT_RANDOM_MULTIPLIER_RANGE)
    defense_mult = rng.uniform(*FIGHT_RANDOM_MULTIPLIER_RANGE)
    raw_attack = (
        FIGHT_ATTACK_STRENGTH_WEIGHT * attacker_strength * FIGHT_ATTACK_SIZE_STENGTH_WEIGHT * attacker_size
        + FIGHT_ATTACK_DEXTERITY_WEIGHT * attacker_dexterity
        + FIGHT_ATTACK_AGGRESSIVENESS_WEIGHT * attacker_aggressiveness
    ) * attack_mult
    prevention = (
        FIGHT_DEFENSE_STRENGTH_WEIGHT * defender_strength * FIGHT_ATTACK_SIZE_STENGTH_WEIGHT * defender_size
        + FIGHT_DEFENSE_DEXTERITY_WEIGHT * defender_dexterity
        + FIGHT_DEFENSE_CONSTITUTION_WEIGHT * defender_constitution
    ) * defense_mult
    return max(1, int(raw_attack - prevention))


def _strength_loss_for_round(constitution: int) -> int:
    """Return how much effective strength a pooch loses per round due to fatigue."""
    loss = FIGHT_STRENGTH_LOSS_PER_ROUND / (1 + max(0, constitution) * FIGHT_CONSTITUTION_FATIGUE_REDUCTION)
    return max(1, round(loss))


async def _apply_fight_injury(pooch_id: int, damage: int, rng: random.Random) -> None:
    """Give a fight-appropriate injury to a pooch based on the damage they took in a round."""
    if damage >= FIGHT_SEVERE_BITE_DAMAGE_THRESHOLD:
        bite_name = _FIGHT_INJURY_SEVERE_BITE
        scratch_name = _FIGHT_INJURY_MODERATE_SCRATCH
    elif damage >= FIGHT_MODERATE_BITE_DAMAGE_THRESHOLD:
        bite_name = _FIGHT_INJURY_MODERATE_BITE
        scratch_name = _FIGHT_INJURY_MINOR_SCRATCH
    else:
        bite_name = _FIGHT_INJURY_MINOR_BITE
        scratch_name = _FIGHT_INJURY_MINOR_SCRATCH

    injury_name = bite_name if rng.random() < FIGHT_INJURY_BITE_CHANCE else scratch_name
    injury = await get_injury_by_name(injury_name)
    if injury is not None:
        await add_injury_to_pooch(pooch_id, injury.id)


async def handle_fight_pooches(
    attacker_id: int,
    defender_id: int,
    rounds: int = FIGHT_ROUNDS,
    defender_strength_bonus: int = FIGHT_DEFENDER_STRENGTH_BONUS,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """
    Simulate a fight between two pooches, applying injuries each round.

    Returns a dict with attacker_id, defender_id, attacker_damage, defender_damage,
    attacker_died, defender_died, winner_id, draw, rounds_fought.
    """
    rng = rng if rng is not None else random.Random()

    attacker = await get_pooch_by_id(attacker_id)
    defender = await get_pooch_by_id(defender_id)

    if attacker is None or defender is None or not attacker.alive or not defender.alive:
        return {
            "attacker_id": attacker_id,
            "defender_id": defender_id,
            "attacker_damage": 0,
            "defender_damage": 0,
            "attacker_died": False,
            "defender_died": False,
            "winner_id": None,
            "draw": True,
            "rounds_fought": 0,
            "error": "one or both pooches unavailable",
        }

    att_str: float = max(1, attacker.strength)
    att_dex = max(1, attacker.dexterity)
    att_con = max(1, attacker.constitution)
    att_agg = max(1, attacker.aggressiveness)
    att_siz = max(1, attacker.size)
    def_str_raw: float = max(1, defender.strength)
    def_dex = max(1, defender.dexterity)
    def_con = max(1, defender.constitution)
    def_agg = max(1, defender.aggressiveness)
    def_siz = max(1, defender.size)

    att_fatigue = _strength_loss_for_round(att_con)
    def_fatigue = _strength_loss_for_round(def_con)

    attacker_total_damage = 0
    defender_total_damage = 0
    rounds_fought = 0

    for _ in range(rounds):
        rounds_fought += 1
        def_str_boosted = def_str_raw + defender_strength_bonus

        dmg_to_defender = _compute_damage(
            att_str, att_siz, att_dex, att_agg, def_str_boosted, def_dex, def_con, def_siz, rng
        )
        dmg_to_attacker = _compute_damage(
            def_str_raw, def_siz, def_dex, def_agg, att_str, att_dex, att_con, att_siz, rng
        )

        attacker_total_damage += dmg_to_attacker
        defender_total_damage += dmg_to_defender

        await _apply_fight_injury(defender_id, dmg_to_defender, rng)
        await _apply_fight_injury(attacker_id, dmg_to_attacker, rng)

        att_str = max(1.0, att_str - att_fatigue)
        def_str_raw = max(1.0, def_str_raw - def_fatigue)

        att_health_remaining = attacker.base_health - attacker_total_damage
        def_health_remaining = defender.base_health - defender_total_damage
        if att_health_remaining <= 0 or def_health_remaining <= 0:
            break

    if attacker_total_damage > 0:
        await modify_pooch_base_health(attacker_id, -attacker_total_damage)
    if defender_total_damage > 0:
        await modify_pooch_base_health(defender_id, -defender_total_damage)

    att_died = (attacker.base_health - attacker_total_damage) <= 0
    def_died = (defender.base_health - defender_total_damage) <= 0

    if att_died:
        await set_pooch_dead(attacker_id)
    if def_died:
        await set_pooch_dead(defender_id)

    if att_died and def_died:
        winner_id = None
        draw = True
    elif att_died:
        winner_id = defender_id
        draw = False
    elif def_died:
        winner_id = attacker_id
        draw = False
    elif attacker_total_damage == defender_total_damage:
        winner_id = None
        draw = True
    elif defender_total_damage > attacker_total_damage:
        winner_id = attacker_id
        draw = False
    else:
        winner_id = defender_id
        draw = False

    return {
        "attacker_id": attacker_id,
        "defender_id": defender_id,
        "attacker_damage": attacker_total_damage,
        "defender_damage": defender_total_damage,
        "attacker_died": att_died,
        "defender_died": def_died,
        "winner_id": winner_id,
        "draw": draw,
        "rounds_fought": rounds_fought,
    }
