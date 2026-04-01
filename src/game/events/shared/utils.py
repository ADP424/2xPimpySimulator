"""
Shared helpers for pooch creation, cloning, breeding, and placement that are common
across all three event systems (owner, server, stray).
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from src.database import (
    add_mutation_to_pooch,
    add_pooch_breeds,
    add_pooch_to_kennel,
    add_pooch_to_vendor_stock,
    copy_pooch_injuries,
    get_random_breed_ids,
    list_kennels_for_owner,
    list_owners,
    list_pooch_breed_weights,
    list_pooch_mutations,
    list_pooches_for_kennel,
    list_vendors,
    modify_pooch_age,
    modify_pooch_base_health,
    remove_pooch_from_strays,
    rename_pooch,
    set_pooch_breeding_cooldown,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
)
from src.game.manage_auctions import cancel_listing_for_pooch

logger = logging.getLogger(__name__)


async def deliver_to_any_kennel(pooch_id: int, server_discord_id: int, rng: random.Random) -> bool:
    """Remove a pooch from strays and place it in a random kennel with free space across all owners.

    Returns True on success.
    """
    owners = await list_owners()
    rng.shuffle(owners)
    for owner in owners:
        kennels = await list_kennels_for_owner(owner.discord_id)
        for kennel in kennels:
            pooches_in = await list_pooches_for_kennel(kennel.id)
            if len(pooches_in) < kennel.pooch_limit:
                await remove_pooch_from_strays(pooch_id)
                await cancel_listing_for_pooch(pooch_id)
                await transfer_pooch_to_owner(pooch_id, owner.discord_id)
                await add_pooch_to_kennel(kennel.id, pooch_id)
                return True
    return False


async def deliver_to_vendor(pooch_id: int, server_discord_id: int, rng: random.Random) -> bool:
    """Remove a pooch from strays and add it to a random vendor's stock on the server.

    Returns True on success.
    """
    vendors = await list_vendors(server_discord_id)
    if not vendors:
        return False
    vendor = rng.choice(vendors)
    await remove_pooch_from_strays(pooch_id)
    await cancel_listing_for_pooch(pooch_id)
    await transfer_pooch_to_vendor(pooch_id, vendor.id)
    await add_pooch_to_vendor_stock(vendor.id, pooch_id)
    return True


async def build_pooch_kwargs(parameters: dict[str, Any], rng: random.Random, season: Optional[str] = None) -> dict:
    """Build kwargs dict for create_pooch from event action parameters."""
    kwargs: dict[str, Any] = {"rng": rng}
    for key in (
        "name",
        "sex",
        "age",
        "base_health",
        "strength",
        "cuteness",
        "fluffiness",
        "intelligence",
        "dexterity",
        "fertility",
        "aggressiveness",
        "constitution",
        "breeding_cooldown",
    ):
        if key in parameters:
            kwargs[key] = parameters[key]

    breeds_param = parameters.get("breeds")
    if isinstance(breeds_param, list):
        kwargs["breeds"] = breeds_param
    elif isinstance(breeds_param, int) and breeds_param > 0:
        kwargs["breeds"] = await get_random_breed_ids(breeds_param, rng=rng, season=season)

    mutations_param = parameters.get("mutations")
    if isinstance(mutations_param, list):
        kwargs["mutations"] = mutations_param

    return kwargs


async def apply_random_mutations(
    pooch_id: int, mutations_param: Any, rng: random.Random, season: Optional[str] = None
) -> None:
    """If mutations_param is an int, roll that many random mutations onto the pooch."""
    if isinstance(mutations_param, int) and mutations_param > 0:
        for _ in range(mutations_param):
            await add_mutation_to_pooch(pooch_id, rng=rng, season=season)


def build_clone_kwargs(source: Any, parameters: dict[str, Any], rng: random.Random) -> dict:
    """Build kwargs dict for create_pooch when cloning from a source pooch."""
    return {
        "rng": rng,
        "name": parameters.get("name", source.name),
        "sex": parameters.get("sex", source.sex),
        "age": parameters.get("age", source.age),
        "base_health": parameters.get("base_health", source.base_health),
        "strength": parameters.get("strength", source.strength),
        "cuteness": parameters.get("cuteness", source.cuteness),
        "fluffiness": parameters.get("fluffiness", source.fluffiness),
        "intelligence": parameters.get("intelligence", source.intelligence),
        "dexterity": parameters.get("dexterity", source.dexterity),
        "fertility": parameters.get("fertility", source.fertility),
        "aggressiveness": parameters.get("aggressiveness", source.aggressiveness),
        "constitution": parameters.get("constitution", source.constitution),
        "size": source.size,
        "breeding_cooldown": parameters.get("breeding_cooldown", source.breeding_cooldown),
    }


async def copy_pooch_genetics(source_id: int, clone_id: int) -> None:
    """Copy breed weights, mutations, and injuries from source to clone."""
    breed_weights = await list_pooch_breed_weights(source_id)
    if breed_weights:
        await add_pooch_breeds(clone_id, dict(breed_weights))
    for mut in await list_pooch_mutations(source_id):
        await add_mutation_to_pooch(clone_id, mutation_id=mut.id)
    await copy_pooch_injuries(source_id, clone_id)


async def apply_baby_overrides(baby_id: int, parameters: dict[str, Any]) -> None:
    """Apply optional name/age/health/cooldown overrides to a newly bred baby pooch."""
    if "baby_name" in parameters:
        await rename_pooch(baby_id, str(parameters["baby_name"]))
    if "baby_age" in parameters:
        await modify_pooch_age(baby_id, parameters["baby_age"])
    if "baby_base_health" in parameters:
        await modify_pooch_base_health(baby_id, parameters["baby_base_health"])
    if "baby_breeding_cooldown" in parameters:
        await set_pooch_breeding_cooldown(baby_id, parameters["baby_breeding_cooldown"])


def resolve_save_as_specs(save_as_raw: Any) -> list[dict[str, str]]:
    """Normalise the save_as parameter into a list of {slot, target} dicts."""
    if isinstance(save_as_raw, str):
        return [{"slot": save_as_raw, "target": "clone"}]
    elif isinstance(save_as_raw, list):
        return [s for s in save_as_raw if isinstance(s, dict)]
    return []
