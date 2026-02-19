from __future__ import annotations

import random
from collections import deque
from typing import Optional

from database import (
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
    set_pooch_breeding_cooldown,
    set_pooch_parentage,
    set_pooch_virgin,
)

from .constants import (
    NUM_INCEST_MUTATION_ROLLS,
    POOCH_BASE_HEALTH_RANGE,
    POOCH_BREEDING_COOLDOWN,
    POOCH_FETAL_AGE,
    TRIPLETS_CHANCE,
    TWINS_CHANCE,
)
from .exceptions.pooch_not_found import PoochNotFound
from .utils import get_pooch_mutation_advanced_option_total


def _combine_puppy_name(father_name: str, mother_name: str) -> str:
    father_name = father_name
    mother_name = mother_name
    left = father_name[: max(len(father_name) // 2, 1)]
    right = mother_name[len(mother_name) // 2 :]
    name = (left + right).strip()
    return name


async def calculate_incest_level(first_pooch_id: int, second_pooch_id: int, max_depth: int = 8) -> float:
    """
    Calculate the level of incest between two pooches based on family distance.

    Parameters
    ----------
    first_pooch_id: int
        The ID of the starting pooch.

    second_pooch_id: int
        The ID of the ending pooch.

    Returns
    -------
    float
        The relative incest between the two pooches.

    Notes
    -----
    Distance is computed as the shortest number of "jumps" where a jump is:
      - child <-> parent
      - full sibling <-> full sibling

    Examples:
      - parent/child or full siblings   => 1 jump => 0.5
      - aunt/uncle <-> niece/nephew     => 2 jumps => 0.25
      - first cousins                   => 3 jumps => 0.125
    """

    if first_pooch_id == second_pooch_id:
        return 0.5

    # Bape-First-Search
    parents_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}
    children_cache: dict[int, list[int]] = {}
    siblings_cache: dict[int, list[int]] = {}

    async def neighbors(node_id: int) -> list[int]:
        out: list[int] = []

        if node_id not in parents_cache:
            father, mother = await database_get_parents(node_id)
            parents_cache[node_id] = (father, mother)
        father, mother = parents_cache[node_id]
        if father is not None:
            out.append(father)
        if mother is not None:
            out.append(mother)

        if node_id not in children_cache:
            children_cache[node_id] = [child.id for child in await list_pooch_children(node_id)]
        out.extend(children_cache[node_id])

        if node_id not in siblings_cache:
            siblings_cache[node_id] = [sibling.id for sibling in await list_pooch_siblings(node_id)]
        out.extend(siblings_cache[node_id])

        seen: set[int] = set()
        deduped: list[int] = []
        for pooch_id in out:
            if pooch_id not in seen:
                seen.add(pooch_id)
                deduped.append(pooch_id)

        return deduped

    async def database_get_parents(child_id: int) -> tuple[Optional[int], Optional[int]]:
        father, mother = await get_pooch_parents(child_id)
        return (father.id if father is not None else None, mother.id if mother is not None else None)

    queue = deque([(first_pooch_id, 0)])
    visited: set[int] = {first_pooch_id}

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor in await neighbors(node):
            if neighbor == second_pooch_id:
                jumps = depth + 1
                return 0.5**jumps
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return 0.0


async def breed_pooches(first_pooch_id: int, second_pooch_id: int, rng_seed: Optional[int] = None) -> list[int]:
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
    if first_pooch is None:
        raise PoochNotFound(first_pooch_id)
    if second_pooch is None:
        raise PoochNotFound(second_pooch_id)

    if first_pooch.sex == second_pooch.sex:
        raise ValueError("Pooches must be different sexes to breed.")

    if first_pooch.sex == "male":
        father, mother = first_pooch, second_pooch
    else:
        father, mother = second_pooch, first_pooch

    if father.breeding_cooldown > 0 or mother.breeding_cooldown > 0:
        raise ValueError("One or both pooches are still on breeding cooldown.")

    await set_pooch_breeding_cooldown(
        father.id,
        max(
            POOCH_BREEDING_COOLDOWN + await get_pooch_mutation_advanced_option_total(father.id, "breeding_cooldown"), 0
        ),
    )
    await set_pooch_breeding_cooldown(
        mother.id,
        max(
            POOCH_BREEDING_COOLDOWN + await get_pooch_mutation_advanced_option_total(mother.id, "breeding_cooldown"), 0
        ),
    )
    await set_pooch_virgin(father.id)
    await set_pooch_virgin(mother.id)

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

    for _ in range(litter_size):
        puppy_name = _combine_puppy_name(father.name, mother.name)
        puppy = await create_pooch(
            owner_discord_id=mother.owner_discord_id,
            name=puppy_name,
            age=POOCH_FETAL_AGE,
            base_health=rng.randint(POOCH_BASE_HEALTH_RANGE[0], POOCH_BASE_HEALTH_RANGE[1]),
            rng=rng,
        )

        await set_pooch_parentage(puppy.id, father_id=father.id, mother_id=mother.id)
        await create_pooch_pregnancy(mother.id, puppy.id)

        # The child gets 50% of the breeds from each parent
        merged: dict[int, float] = {}
        for breed_id, weight in father_breeds.items():
            merged[breed_id] = merged.get(breed_id, 0.0) + (weight * 0.5)
        for breed_id, weight in mother_breeds.items():
            merged[breed_id] = merged.get(breed_id, 0.0) + (weight * 0.5)

        int_weights: dict[int, int] = {}
        for breed_id, weight in merged.items():
            int_weight = round(weight)
            if int_weight <= 0 and weight > 0:
                int_weight = 1
            if int_weight > 0:
                int_weights[breed_id] = int_weight

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

        await set_pooch_breeding_cooldown(
            puppy.id,
            max(
                POOCH_BREEDING_COOLDOWN + await get_pooch_mutation_advanced_option_total(puppy.id, "breeding_cooldown"),
                0,
            ),
        )

        puppies.append(puppy.id)

    return puppies
