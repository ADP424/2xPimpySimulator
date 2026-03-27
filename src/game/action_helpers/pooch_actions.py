from __future__ import annotations

import logging
import random
from typing import Any, Optional

from src.database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    damn_pooch,
    get_mutation_by_name,
    get_pooch_by_id,
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
    FIGHT_ATTACK_STRENGTH_WEIGHT,
    FIGHT_DEFENDER_STRENGTH_BONUS,
    FIGHT_DEFENSE_DEXTERITY_WEIGHT,
    FIGHT_DEFENSE_SIZE_WEIGHT,
    FIGHT_DEFENSE_STRENGTH_WEIGHT,
    FIGHT_RANDOM_MULTIPLIER_RANGE,
    FIGHT_ROUNDS,
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
    """Handle modify_base_health / modify_pooch_health."""
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
            result.pooches_killed.append(pooch_id)
    if result.pooches_killed:
        count = len(result.pooches_killed)
        result.message = "A pooch has died!" if count == 1 else f"{count} pooches have died!"


async def handle_add_mutation(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle add_mutation."""
    mutation_id = parameters.get("mutation_id")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    min_health_impact = parameters.get("min_health_impact")
    max_health_impact = parameters.get("max_health_impact")
    for pooch_id in pooch_ids:
        if mutation_id:
            await add_mutation_to_pooch(pooch_id, mutation_id)
        else:
            await add_mutation_to_pooch(
                pooch_id,
                rng=rng,
                min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                max_rarity=max_rarity if isinstance(max_rarity, str) else None,
                min_health_impact=min_health_impact if isinstance(min_health_impact, str) else None,
                max_health_impact=max_health_impact if isinstance(max_health_impact, str) else None,
            )
        result.pooches_affected.append(pooch_id)


async def handle_add_mutation_by_name(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle add_mutation with name lookup (stray variant)."""
    mutation_name = parameters.get("mutation")
    mutation_id = parameters.get("mutation_id")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    min_health_impact = parameters.get("min_health_impact")
    max_health_impact = parameters.get("max_health_impact")
    for pooch_id in pooch_ids:
        if mutation_name:
            mut = await get_mutation_by_name(str(mutation_name))
            if mut:
                await add_mutation_to_pooch(pooch_id, mut.id)
        elif mutation_id:
            await add_mutation_to_pooch(pooch_id, mutation_id)
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
    """Handle remove_mutation."""
    mutation_id = parameters.get("mutation_id")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    min_health_impact = parameters.get("min_health_impact")
    max_health_impact = parameters.get("max_health_impact")
    for pooch_id in pooch_ids:
        if mutation_id:
            removed = await remove_mutation_from_pooch(pooch_id, mutation_id)
        else:
            removed = await remove_random_mutation_from_pooch(
                pooch_id,
                rng=rng,
                min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                max_rarity=max_rarity if isinstance(max_rarity, str) else None,
                min_health_impact=min_health_impact if isinstance(min_health_impact, str) else None,
                max_health_impact=max_health_impact if isinstance(max_health_impact, str) else None,
            )
        if removed:
            result.mutations_removed.append((pooch_id, removed.mutation_id))
            result.pooches_affected.append(pooch_id)


async def handle_remove_mutation_by_name(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle remove_mutation with name lookup (stray variant)."""
    mutation_name = parameters.get("mutation")
    mutation_id = parameters.get("mutation_id")
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
        elif mutation_id:
            removed = await remove_mutation_from_pooch(pooch_id, mutation_id)
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
            result.pooches_affected.append(pooch_id)


async def handle_add_breed(
    pooch_ids: list[int],
    parameters: dict[str, Any],
    rng: random.Random,
    result: Any,
) -> None:
    """Handle add_breed."""
    breed_id = parameters.get("breed_id")
    weight = parameters.get("weight", 0.5)
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    for pooch_id in pooch_ids:
        if breed_id:
            await add_breed_to_pooch(pooch_id, breed_id, weight=weight)
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
    """Handle remove_breed."""
    breed_id = parameters.get("breed_id")
    min_rarity = parameters.get("min_rarity")
    max_rarity = parameters.get("max_rarity")
    for pooch_id in pooch_ids:
        if breed_id:
            removed = await remove_breed_from_pooch(pooch_id, breed_id)
        else:
            removed = await remove_random_breed_from_pooch(
                pooch_id,
                rng=rng,
                min_rarity=min_rarity if isinstance(min_rarity, str) else None,
                max_rarity=max_rarity if isinstance(max_rarity, str) else None,
            )
        if removed:
            result.pooches_affected.append(pooch_id)


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
        await set_pooch_dead(pooch_id)
        hell_entry = await damn_pooch(pooch_id)
        if hell_entry:
            result.pooches_killed.append(pooch_id)
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
    """Handle modify_breeding_cooldown / set_breeding_cooldown."""
    mode = get_mode(parameters)
    if "cooldown" in parameters and "amount" not in parameters and "min_amount" not in parameters:
        cooldown = parameters["cooldown"]
        for pooch_id in pooch_ids:
            if isinstance(cooldown, str) and cooldown.strip().lower() == "base":
                await reset_pooch_breeding_cooldown(pooch_id, base_cooldown=_get_breeding_cooldown_default())
            else:
                await set_pooch_breeding_cooldown(pooch_id, int(cooldown))
            result.pooches_affected.append(pooch_id)
    else:
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

# Damage formula per round:
#   raw_attack   = (ATTACK_STRENGTH_WEIGHT * strength + ATTACK_AGGRESSIVENESS_WEIGHT * aggressiveness)
#                  * uniform(RANDOM_MULTIPLIER_RANGE)
#   prevention   = (DEFENSE_STRENGTH_WEIGHT * strength + DEFENSE_SIZE_WEIGHT * size)
#                  * uniform(RANDOM_MULTIPLIER_RANGE)
#   damage_dealt = max(1, int(raw_attack - prevention))
#
# Defender advantage: the defending pooch's effective strength for mitigation
# is increased by defender_strength_bonus (default: FIGHT_DEFENDER_STRENGTH_BONUS).
#
# The fight runs for a fixed number of rounds.  Each round, both pooches
# simultaneously deal damage to one another.  The fight ends early if either
# pooch's health reaches 0 or below.
#
# Outcome:
#   - If both alive: winner is the one with less total damage taken.
#   - If one dies: the survivor wins.
#   - If both die in the same round: draw.
#   - If total_damage_taken is equal and both survive: draw.
#
# The action applies the damage directly to base_health via modify_pooch_base_health.
# It does NOT determine the event winner — that is up to the caller.


def _compute_damage(
    attacker_strength: int,
    attacker_dexterity: int,
    attacker_aggressiveness: int,
    defender_strength: int,
    defender_dexterity: int,
    defender_size: int,
    rng: random.Random,
) -> int:
    """
    Return integer damage dealt in one round.
    """

    attack_mult = rng.uniform(*FIGHT_RANDOM_MULTIPLIER_RANGE)
    defense_mult = rng.uniform(*FIGHT_RANDOM_MULTIPLIER_RANGE)
    raw_attack = (
        FIGHT_ATTACK_STRENGTH_WEIGHT * attacker_strength
        + FIGHT_ATTACK_DEXTERITY_WEIGHT * attacker_dexterity
        + FIGHT_ATTACK_AGGRESSIVENESS_WEIGHT * attacker_aggressiveness
    ) * attack_mult
    prevention = (
        FIGHT_DEFENSE_STRENGTH_WEIGHT * defender_strength
        + FIGHT_DEFENSE_DEXTERITY_WEIGHT * defender_dexterity
        + FIGHT_DEFENSE_SIZE_WEIGHT * defender_size
    ) * defense_mult
    return max(1, int(raw_attack - prevention))


async def handle_fight_pooches(
    attacker_id: int,
    defender_id: int,
    rounds: int = FIGHT_ROUNDS,
    defender_strength_bonus: int = FIGHT_DEFENDER_STRENGTH_BONUS,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """
    Simulate a fight between two pooches and apply the resulting health loss.

    Args:
        rounds:                  number of fight rounds
        defender_strength_bonus: extra effective strength added to defender's mitigation only

    Returns a dict:
        {
            "attacker_id":         int,
            "defender_id":         int,
            "attacker_damage":     int,   # total damage taken by attacker
            "defender_damage":     int,   # total damage taken by defender
            "attacker_died":       bool,
            "defender_died":       bool,
            "winner_id":           int | None,  # None on draw
            "draw":                bool,
            "rounds_fought":       int,
        }
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

    att_str = max(1, attacker.strength)
    att_dex = max(1, attacker.dexterity)
    att_agg = max(1, attacker.aggressiveness)
    att_siz = max(1, attacker.size)
    def_str_raw = max(1, defender.strength)
    def_str_boosted = def_str_raw + defender_strength_bonus  # only for defender's mitigation
    def_dex = max(1, defender.dexterity)
    def_agg = max(1, defender.aggressiveness)
    def_siz = max(1, defender.size)

    attacker_total_damage = 0
    defender_total_damage = 0
    rounds_fought = 0

    for _ in range(rounds):
        rounds_fought += 1

        # Simultaneous damage — each pooch attacks and defends in the same round
        dmg_to_defender = _compute_damage(att_str, att_dex, att_agg, def_str_boosted, def_dex, def_siz, rng)
        dmg_to_attacker = _compute_damage(def_str_raw, def_dex, def_agg, att_str, att_dex, att_siz, rng)

        attacker_total_damage += dmg_to_attacker
        defender_total_damage += dmg_to_defender

        # Check for early death after this round
        att_health_remaining = attacker.base_health - attacker_total_damage
        def_health_remaining = defender.base_health - defender_total_damage
        if att_health_remaining <= 0 or def_health_remaining <= 0:
            break

    # Apply health changes
    if attacker_total_damage > 0:
        await modify_pooch_base_health(attacker_id, -attacker_total_damage)
    if defender_total_damage > 0:
        await modify_pooch_base_health(defender_id, -defender_total_damage)

    # Determine deaths (based on starting health, not post-modification DB state)
    att_died = (attacker.base_health - attacker_total_damage) <= 0
    def_died = (defender.base_health - defender_total_damage) <= 0

    if att_died:
        await set_pooch_dead(attacker_id)
    if def_died:
        await set_pooch_dead(defender_id)

    # Determine winner
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
        # Attacker took less damage → attacker wins (defender dealt more damage, attacker dealt more)
        # Defender took more damage → defender is worse off
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
