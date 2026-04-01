from __future__ import annotations

import random
from collections import deque
from typing import Optional

from src.database import (
    add_mutation_to_pooch,
    add_pooch_breeds,
    create_pooch,
    create_pooch_pregnancy,
    get_pooch_by_id,
    get_pooch_parents,
    list_pooch_breed_weights,
    list_pooch_children,
    list_pooch_mutations,
    list_pooch_siblings,
    reset_pooch_breeding_cooldown,
    set_pooch_parentage,
    set_pooch_virgin,
)

from .constants import (
    BREED_NOISE_RANGE,
    NUM_INCEST_MUTATION_ROLLS,
    POOCH_BREEDING_COOLDOWN,
    POOCH_FETAL_AGE,
    POOCH_STATS,
    SHARED_BREED_WEIGHT_BONUS,
    TRIPLETS_CHANCE,
    TWINS_CHANCE,
)
from .exceptions import PoochNotFound


def combine_puppy_name(father_name: str, mother_name: str) -> str:
    """
    Combine puppy name.

    Parameters
    ----------
    father_name: Any
        The `father_name` value.

    mother_name: Any
        The `mother_name` value.

    Returns
    -------
    Any
        The result of calling `combine_puppy_name`.
    """

    father_name = father_name
    mother_name = mother_name
    left = father_name[: max(len(father_name) // 2, 1)]
    right = mother_name[len(mother_name) // 2 :]
    name = (left + right).strip()
    return name


async def breed_pooches(
    first_pooch_id: int, second_pooch_id: int, rng_seed: Optional[int] = None, skip_validation=False
) -> list[int]:
    """
    Breed two pooches and create a fetus in the mother.

    Parameters
    ----------
    first_pooch_id: int
        The ID of the first pooch to breed.

    second_pooch_id: int
        The ID of the second pooch to breed.

    rng_seed: int, optional
        The seed to use to randomize random values with.

    skip_validation: bool, default : False
        Whether to skip validation (like pooches being different sexes, on breeding cooldown, etc.) or not.

    Returns
    -------
    list[int]
        A list of the new pooch IDs.

    Raises
    ------
    PoochNotFound
        When one of the pooch IDs provided doesn't link to a real pooch.

    ValueError
        When the pooches provided are the same sex, or one or both are still on breeding cooldown.
    """

    rng = random.Random(rng_seed)

    first_pooch = await get_pooch_by_id(first_pooch_id)
    second_pooch = await get_pooch_by_id(second_pooch_id)
    if first_pooch is None and not skip_validation:
        raise PoochNotFound(first_pooch_id)
    if second_pooch is None and not skip_validation:
        raise PoochNotFound(second_pooch_id)

    if first_pooch.sex == second_pooch.sex and not skip_validation:
        raise ValueError("Pooches must be different sexes to breed.")

    if first_pooch.sex == "male":
        father, mother = first_pooch, second_pooch
    else:
        father, mother = second_pooch, first_pooch

    if (father.breeding_cooldown > 0 or mother.breeding_cooldown > 0) and not skip_validation:
        raise ValueError("One or both pooches are still on breeding cooldown.")

    await reset_pooch_breeding_cooldown(father.id, base_cooldown=POOCH_BREEDING_COOLDOWN)
    await reset_pooch_breeding_cooldown(mother.id, base_cooldown=POOCH_BREEDING_COOLDOWN)
    await set_pooch_virgin(father.id, False)
    await set_pooch_virgin(mother.id, False)

    roll = rng.random()
    litter_size = 3 if roll < TRIPLETS_CHANCE else (2 if roll < TWINS_CHANCE else 1)

    incest_level = await calculate_incest_level(father.id, mother.id)

    father_breeds = dict(await list_pooch_breed_weights(father.id))
    mother_breeds = dict(await list_pooch_breed_weights(mother.id))

    father_mutations = await list_pooch_mutations(father.id)
    mother_mutations = await list_pooch_mutations(mother.id)

    father_mutation_ids = {mutation.id: mutation for mutation in father_mutations}
    mother_mutation_ids = {mutation.id: mutation for mutation in mother_mutations}
    all_mutation_ids = set(father_mutation_ids) | set(mother_mutation_ids)

    puppies: list[int] = []

    def _inherit_stat(parent_a: int, parent_b: int) -> int:
        lo = min(parent_a, parent_b)
        hi = max(parent_a, parent_b)
        return max(0, rng.randint(lo - 1, hi + 1))

    for _ in range(litter_size):
        puppy_name = combine_puppy_name(father.name, mother.name)
        inherited_base_health = _inherit_stat(father.base_health, mother.base_health)
        inherited_stats = {stat: _inherit_stat(getattr(father, stat), getattr(mother, stat)) for stat in POOCH_STATS}
        inherited_size = _inherit_stat(father.size, mother.size)
        puppy = await create_pooch(
            owner_discord_id=mother.owner_discord_id,
            name=puppy_name,
            age=POOCH_FETAL_AGE,
            base_health=inherited_base_health,
            size=inherited_size,
            **inherited_stats,
            rng=rng,
        )

        effective_father_id = None if father.id == mother.id else father.id
        await set_pooch_parentage(puppy.id, father_id=effective_father_id, mother_id=mother.id)
        await create_pooch_pregnancy(mother.id, puppy.id)

        # The child gets 50% of the breeds from each parent (normalized first)
        father_total = sum(father_breeds.values())
        mother_total = sum(mother_breeds.values())
        budget = max(father_total, mother_total, 1)

        merged: dict[int, float] = {}

        if father_total > 0:
            for breed_id, weight in father_breeds.items():
                merged[breed_id] = merged.get(breed_id, 0.0) + (0.5 * (weight / father_total) * budget)

        if mother_total > 0:
            for breed_id, weight in mother_breeds.items():
                merged[breed_id] = merged.get(breed_id, 0.0) + (0.5 * (weight / mother_total) * budget)

        # Boost breeds shared by both parents
        shared_breeds = set(father_breeds) & set(mother_breeds)
        for breed_id in shared_breeds:
            if breed_id in merged:
                merged[breed_id] *= SHARED_BREED_WEIGHT_BONUS

        # Apply random noise to each breed weight
        for breed_id in merged:
            merged[breed_id] *= rng.uniform(*BREED_NOISE_RANGE)

        scalar = 1 / min(merged.values())

        int_weights: dict[int, int] = {}
        for breed_id, weight in merged.items():
            int_weight = round(scalar * weight)
            if int_weight <= 0 and weight > 0:
                int_weight = 1
            if int_weight > 0:
                int_weights[breed_id] = int_weight

        # Drop breeds whose weight is less than 1% of the total
        total_weight = sum(int_weights.values())
        int_weights = {bid: w for bid, w in int_weights.items() if w / total_weight >= 0.01}

        await add_pooch_breeds(puppy.id, int_weights)

        # The child has a chance to inherit mutations equal to the mutation's heritability,
        # or double that if both parents have it
        for mutation_id in all_mutation_ids:
            mutation = father_mutation_ids.get(mutation_id) or mother_mutation_ids.get(mutation_id)
            if mutation is None:
                continue
            heritability = mutation.heritability
            if mutation_id in father_mutation_ids and mutation_id in mother_mutation_ids:
                heritability = min(1.0, heritability * 2.0)
            if rng.random() < heritability:
                await add_mutation_to_pooch(puppy.id, mutation_id=mutation_id, rng=rng)

        # Randomly mutate based on the level of incest
        for _ in range(NUM_INCEST_MUTATION_ROLLS):
            if incest_level > 0 and rng.random() < incest_level:
                await add_mutation_to_pooch(puppy.id, rng=rng)

        await reset_pooch_breeding_cooldown(puppy.id, base_cooldown=POOCH_BREEDING_COOLDOWN)

        puppies.append(puppy.id)

    return puppies


async def calculate_incest_level(first_pooch_id: int, second_pooch_id: int, max_depth: int = 8) -> float:
    """
    Calculate incest level.

    Parameters
    ----------
    first_pooch_id: Any
        The `first_pooch_id` value.

    second_pooch_id: Any
        The `second_pooch_id` value.

    max_depth: Any
        The `max_depth` value.

    Returns
    -------
    Any
        The result of calling `calculate_incest_level`.
    """

    if first_pooch_id == second_pooch_id:
        return 1.0

    parents_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}
    children_cache: dict[int, list[int]] = {}
    siblings_cache: dict[int, list[int]] = {}

    async def database_get_parents(child_id: int) -> tuple[Optional[int], Optional[int]]:
        father, mother = await get_pooch_parents(child_id)
        return (father.id if father is not None else None, mother.id if mother is not None else None)

    async def neighbors(node_id: int, prev_id: Optional[int]) -> list[int]:
        out: list[int] = []

        if node_id not in parents_cache:
            parents_cache[node_id] = await database_get_parents(node_id)
        father, mother = parents_cache[node_id]

        # Prevent pooches with a shared child from being counted as being related
        parent_ids = [parent for parent in (father, mother) if parent is not None]
        if prev_id is not None and prev_id in parent_ids:
            parent_ids = [prev_id]
        out.extend(parent_ids)

        # Children
        if node_id not in children_cache:
            children_cache[node_id] = [c.id for c in await list_pooch_children(node_id)]
        out.extend(children_cache[node_id])

        # Siblings
        if node_id not in siblings_cache:
            siblings_cache[node_id] = [s.id for s in await list_pooch_siblings(node_id)]
        out.extend(siblings_cache[node_id])

        seen: set[int] = set()
        deduped: list[int] = []
        for pooch_id in out:
            if pooch_id not in seen:
                seen.add(pooch_id)
                deduped.append(pooch_id)
        return deduped

    queue = deque([(first_pooch_id, None, 0)])
    visited: set[int] = {first_pooch_id}

    while queue:
        node, prev, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for neighbor_id in await neighbors(node, prev):
            if neighbor_id == second_pooch_id:
                jumps = depth + 1
                return 0.5**jumps

            if neighbor_id not in visited:
                visited.add(neighbor_id)
                queue.append((neighbor_id, node, depth + 1))

    return 0.0
