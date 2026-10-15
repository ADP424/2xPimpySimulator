"""
Blood-magic rituals: clone, rejuvenation, gender change, immortality.

All rituals share a common shape:
- Validate ownership.
- Validate the pooch is alive.
- Verify the owner can afford the bloodskull / body-part costs.
- Mutate DB.
- Return ``(success, message, before_snapshot, after_snapshot)`` so the UI
  can render meaningful before/after output.

Costs and effects live in ``src/game/constants.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.database import (
    add_breed_to_pooch,
    add_mutation_to_pooch,
    create_pooch,
    flip_pooch_sex,
    get_owner_by_discord_id,
    get_pooch_by_id,
    give_bloodskulls_to_owner,
    give_owner_body_part,
    increment_pooch_rejuvenation_count,
    list_kennels_for_owner,
    list_pooch_breed_weights,
    list_pooch_mutations,
    list_pooches_for_kennel,
    set_pooch_age,
    set_pooch_immortal,
)
from src.logger import get_logger

from .constants import (
    CLONE_RITUAL_BLOODSKULLS_MIN,
    CLONE_RITUAL_BLOODSKULLS_VALUE_MULT,
    CLONE_RITUAL_BRAIN_COST,
    CLONE_RITUAL_HEART_COST,
    GENDER_CHANGE_RITUAL_BLOODSKULLS,
    GENDER_CHANGE_RITUAL_EYE_COST,
    IMMORTALITY_RITUAL_BLOODSKULLS,
    IMMORTALITY_RITUAL_BRAIN_COST,
    IMMORTALITY_RITUAL_EYE_COST,
    IMMORTALITY_RITUAL_HEART_COST,
    IMMORTALITY_RITUAL_TAIL_COST,
    REJUVENATION_RITUAL_BLOODSKULLS,
    REJUVENATION_RITUAL_HEART_COST,
)
from .manage_hell import get_pooch_bloodskull_value
from .manage_kennels import add_pooch_to_kennel

logger = get_logger("game/manage_rituals")


@dataclass
class RitualResult:
    success: bool
    message: str
    source_pooch_id: Optional[int] = None
    result_pooch_id: Optional[int] = None
    cost_breakdown: dict = field(default_factory=dict)


# What each ritual costs (clone's bloodskulls also scale with the pooch's value; see clone_ritual_cost)
RITUAL_COSTS: dict[str, dict[str, int]] = {
    "clone": {
        "bloodskulls": CLONE_RITUAL_BLOODSKULLS_MIN,
        "brains": CLONE_RITUAL_BRAIN_COST,
        "hearts": CLONE_RITUAL_HEART_COST,
    },
    "rejuvenate": {"bloodskulls": REJUVENATION_RITUAL_BLOODSKULLS, "hearts": REJUVENATION_RITUAL_HEART_COST},
    "gender-change": {"bloodskulls": GENDER_CHANGE_RITUAL_BLOODSKULLS, "eyes": GENDER_CHANGE_RITUAL_EYE_COST},
    "immortalize": {
        "bloodskulls": IMMORTALITY_RITUAL_BLOODSKULLS,
        "hearts": IMMORTALITY_RITUAL_HEART_COST,
        "brains": IMMORTALITY_RITUAL_BRAIN_COST,
        "eyes": IMMORTALITY_RITUAL_EYE_COST,
        "tails": IMMORTALITY_RITUAL_TAIL_COST,
    },
}

_PART_NAMES = {
    "hearts": ("heart", "hearts"),
    "brains": ("brain", "brains"),
    "eyes": ("eye", "eyes"),
    "tails": ("tail", "tails"),
}


def describe_ritual_costs() -> dict[str, str]:
    """Player-facing cost of each ritual, e.g. ``{"rejuvenate": "150 bloodskulls + 1 heart"}``."""
    described = {}
    for ritual, costs in RITUAL_COSTS.items():
        parts = [f"{costs['bloodskulls']}{'+' if ritual == 'clone' else ''} bloodskulls"]
        for part, (one, many) in _PART_NAMES.items():
            if costs.get(part):
                parts.append(f"{costs[part]} {one if costs[part] == 1 else many}")
        described[ritual] = " + ".join(parts)
    return described


def clone_ritual_cost(pooch_bloodskull_value: int) -> int:
    return max(
        CLONE_RITUAL_BLOODSKULLS_MIN,
        CLONE_RITUAL_BLOODSKULLS_VALUE_MULT * pooch_bloodskull_value,
    )


async def _check_owner_and_pooch(owner_id: int, pooch_id: int):
    owner = await get_owner_by_discord_id(owner_id)
    if owner is None:
        return None, None, "You don't have an account yet."
    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return owner, None, "Pooch not found."
    if pooch.owner_discord_id != owner_id:
        return owner, None, "That's not your pooch."
    if not pooch.alive:
        return owner, None, "That pooch is dead."
    return owner, pooch, None


def _check_cost(
    owner,
    *,
    bloodskulls: int = 0,
    hearts: int = 0,
    brains: int = 0,
    eyes: int = 0,
    tails: int = 0,
    teeth: int = 0,
) -> Optional[str]:
    if bloodskulls and owner.bloodskulls < bloodskulls:
        return f"Need {bloodskulls} bloodskulls (you have {owner.bloodskulls})."
    if hearts and getattr(owner, "hearts", 0) < hearts:
        return f"Need {hearts} hearts (you have {getattr(owner, 'hearts', 0)})."
    if brains and getattr(owner, "brains", 0) < brains:
        return f"Need {brains} brains (you have {getattr(owner, 'brains', 0)})."
    if eyes and getattr(owner, "eyes", 0) < eyes:
        return f"Need {eyes} eyes (you have {getattr(owner, 'eyes', 0)})."
    if tails and getattr(owner, "tails", 0) < tails:
        return f"Need {tails} tails (you have {getattr(owner, 'tails', 0)})."
    if teeth and getattr(owner, "teeth", 0) < teeth:
        return f"Need {teeth} teeth (you have {getattr(owner, 'teeth', 0)})."
    return None


async def _charge_cost(
    owner_id: int,
    *,
    bloodskulls: int = 0,
    hearts: int = 0,
    brains: int = 0,
    eyes: int = 0,
    tails: int = 0,
    teeth: int = 0,
) -> None:
    if bloodskulls:
        await give_bloodskulls_to_owner(owner_id, -bloodskulls)
    if hearts:
        await give_owner_body_part(owner_id, "heart", -hearts)
    if brains:
        await give_owner_body_part(owner_id, "brain", -brains)
    if eyes:
        await give_owner_body_part(owner_id, "eye", -eyes)
    if tails:
        await give_owner_body_part(owner_id, "tail", -tails)
    if teeth:
        await give_owner_body_part(owner_id, "teeth", -teeth)


# ---------------------------------------------------------------------------
# Clone ritual
# ---------------------------------------------------------------------------


async def clone_pooch_ritual(owner_id: int, pooch_id: int) -> RitualResult:
    """
    Create an age-0 clone of the given pooch. Keeps sex/breeds/mutations and
    base stats; no injuries or diseases. Places it in the owner's first
    available kennel. Returns a ``RitualResult``.
    """
    owner, pooch, err = await _check_owner_and_pooch(owner_id, pooch_id)
    if err:
        return RitualResult(False, err)

    value = await get_pooch_bloodskull_value(pooch.id)
    cost_bs = clone_ritual_cost(value)
    clone_costs = {**RITUAL_COSTS["clone"], "bloodskulls": cost_bs}
    err = _check_cost(owner, **clone_costs)
    if err:
        return RitualResult(False, err)

    # Find a kennel with space.
    target_kennel = None
    for kennel in await list_kennels_for_owner(owner_id):
        if len(await list_pooches_for_kennel(kennel.id)) < kennel.pooch_limit:
            target_kennel = kennel
            break
    if target_kennel is None:
        return RitualResult(False, "You have no kennel with space for a clone.")

    # Capture genetics.
    breeds = await list_pooch_breed_weights(pooch_id)
    mutations = list(await list_pooch_mutations(pooch_id))

    await _charge_cost(owner_id, **clone_costs)

    # Create clone.
    clone = await create_pooch(
        owner_discord_id=owner_id,
        name=f"{pooch.name} II",
        sex=pooch.sex,
        age=0,
        base_health=pooch.base_health,
        strength=pooch.strength,
        cuteness=pooch.cuteness,
        fluffiness=pooch.fluffiness,
        intelligence=pooch.intelligence,
        dexterity=pooch.dexterity,
        fertility=pooch.fertility,
        aggressiveness=pooch.aggressiveness,
        constitution=pooch.constitution,
        size=pooch.size,
    )
    for breed_id, weight in breeds:
        await add_breed_to_pooch(clone.id, breed_id, weight)
    for mut in mutations:
        await add_mutation_to_pooch(clone.id, mut.id)

    await add_pooch_to_kennel(target_kennel.id, clone.id)

    return RitualResult(
        success=True,
        message=f"{pooch.name} has been cloned. Meet {clone.name}!",
        source_pooch_id=pooch.id,
        result_pooch_id=clone.id,
        cost_breakdown=clone_costs,
    )


# ---------------------------------------------------------------------------
# Rejuvenation
# ---------------------------------------------------------------------------


async def rejuvenate_pooch(owner_id: int, pooch_id: int) -> RitualResult:
    owner, pooch, err = await _check_owner_and_pooch(owner_id, pooch_id)
    if err:
        return RitualResult(False, err)

    err = _check_cost(owner, **RITUAL_COSTS["rejuvenate"])
    if err:
        return RitualResult(False, err)

    await _charge_cost(owner_id, **RITUAL_COSTS["rejuvenate"])
    await set_pooch_age(pooch.id, 0)
    new_count = await increment_pooch_rejuvenation_count(pooch.id)
    return RitualResult(
        success=True,
        message=(
            f"{pooch.name} has been rejuvenated to age 0. They now bear "
            f"rejuvenation count {new_count} — each reset permanently weakens "
            "their fertility and constitution."
        ),
        source_pooch_id=pooch.id,
        result_pooch_id=pooch.id,
        cost_breakdown=dict(RITUAL_COSTS["rejuvenate"]),
    )


# ---------------------------------------------------------------------------
# Gender change
# ---------------------------------------------------------------------------


async def gender_change_pooch(owner_id: int, pooch_id: int) -> RitualResult:
    owner, pooch, err = await _check_owner_and_pooch(owner_id, pooch_id)
    if err:
        return RitualResult(False, err)

    if pooch.pregnancy_timer is not None:
        return RitualResult(False, "You cannot change the gender of a pregnant pooch.")

    err = _check_cost(owner, **RITUAL_COSTS["gender-change"])
    if err:
        return RitualResult(False, err)

    await _charge_cost(owner_id, **RITUAL_COSTS["gender-change"])
    new_pooch = await flip_pooch_sex(pooch.id)
    new_sex = new_pooch.sex if new_pooch is not None else ("female" if pooch.sex == "male" else "male")
    return RitualResult(
        success=True,
        message=f"{pooch.name} is now {new_sex}.",
        source_pooch_id=pooch.id,
        result_pooch_id=pooch.id,
        cost_breakdown=dict(RITUAL_COSTS["gender-change"]),
    )


# ---------------------------------------------------------------------------
# Immortality
# ---------------------------------------------------------------------------


async def immortalize_pooch(owner_id: int, pooch_id: int) -> RitualResult:
    owner, pooch, err = await _check_owner_and_pooch(owner_id, pooch_id)
    if err:
        return RitualResult(False, err)

    if getattr(pooch, "immortal", False):
        return RitualResult(False, f"{pooch.name} is already immortal.")

    err = _check_cost(owner, **RITUAL_COSTS["immortalize"])
    if err:
        return RitualResult(False, err)

    await _charge_cost(owner_id, **RITUAL_COSTS["immortalize"])
    await set_pooch_immortal(pooch.id, True)
    return RitualResult(
        success=True,
        message=(
            f"{pooch.name} has crossed the veil. Immortal, ageless, infertile — "
            "they will outlast you, but not injury."
        ),
        source_pooch_id=pooch.id,
        result_pooch_id=pooch.id,
        cost_breakdown=dict(RITUAL_COSTS["immortalize"]),
    )
