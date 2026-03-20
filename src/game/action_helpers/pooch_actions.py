from __future__ import annotations

import logging
import random
from typing import Any, Optional

from src.database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    damn_pooch,
    get_mutation_by_name,
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
