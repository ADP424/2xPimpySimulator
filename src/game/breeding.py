from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from src.database import (
    add_injury_to_pooch,
    add_mutation_to_pooch,
    add_pooch_breeds,
    create_pooch,
    create_pooch_pregnancy,
    create_pooch_snapshot,
    get_injury_by_name,
    get_owner_by_discord_id,
    get_pooch_by_id,
    get_pooch_kennel,
    get_pooch_parents,
    give_money_to_owner,
    list_pooch_breed_weights,
    list_pooch_children,
    list_pooch_injuries,
    list_pooch_mutations,
    list_pooch_siblings,
    list_pooches_for_kennel,
    reset_pooch_breeding_cooldown,
    set_pooch_parentage,
    set_pooch_pregnancy_timer,
    set_pooch_virgin,
)
from src.database.models import SNAPSHOT_BREEDING

from .constants import (
    BREED_NOISE_RANGE,
    NEUTER_COST,
    NUM_INCEST_MUTATION_ROLLS,
    POOCH_BREEDING_COOLDOWN,
    POOCH_FETAL_AGE,
    POOCH_STATS,
    PREGNANCY_TIMER_HOURS_RANGE,
    SHARED_BREED_WEIGHT_BONUS,
    TRIPLETS_CHANCE,
    TWINS_CHANCE,
)
from .exceptions import PoochNotFound
from .manage_diseases import handle_breeding_diseases
from .manage_stats import get_effective_stat


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
    first_pooch_id: int,
    second_pooch_id: int,
    rng_seed: Optional[int] = None,
    skip_validation: bool = False,
    return_disease_events: bool = False,
) -> list[int] | tuple[list[int], list[tuple[int, str, str]]]:
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
        A mother who is already pregnant is refused either way.

    Returns
    -------
    list[int] | tuple[list[int], list[tuple[int, str, str]]]
        The new puppy IDs. When ``return_disease_events`` is True, returns a
        ``(puppy_ids, disease_events)`` tuple instead.

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

    for parent in (father, mother):
        if getattr(parent, "immortal", False) and not skip_validation:
            raise ValueError(f"{parent.name} is immortal, and immortal pooches are infertile.")

    # Checked even with skip_validation: a second litter would overwrite the first one's timer
    if getattr(mother, "pregnancy_timer", None) is not None:
        raise ValueError(f"{mother.name} is already pregnant.")

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

        if merged:
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

    # Disease transmission during breeding (STDs and inheritance)
    from src.database import get_current_season

    _season = await get_current_season()
    disease_events = await handle_breeding_diseases(
        father_id=father.id,
        mother_id=mother.id,
        puppy_ids=puppies,
        season=_season,
        rng=rng,
    )

    # Set the mother's pregnancy timer (Section 7B). The hour loop ticks this
    # down each hour and births the puppies when it hits 0.
    timer = rng.randint(*PREGNANCY_TIMER_HOURS_RANGE)
    await set_pooch_pregnancy_timer(mother.id, timer)

    # Puppies are only counted, not named: they're unborn, and some may never be born
    expecting = f"expecting {len(puppies)} {'puppy' if len(puppies) == 1 else 'puppies'}"
    if father.id == mother.id:
        await create_pooch_snapshot(
            mother.id, SNAPSHOT_BREEDING, f"{mother.name} reproduced asexually and is {expecting}."
        )
    else:
        await create_pooch_snapshot(
            father.id, SNAPSHOT_BREEDING, f"{father.name} bred with {mother.name}, who is {expecting}."
        )
        await create_pooch_snapshot(
            mother.id, SNAPSHOT_BREEDING, f"{mother.name} bred with {father.name} and is {expecting}."
        )

    if return_disease_events:
        return puppies, disease_events
    return puppies


def compute_breeding_chance(intelligence: int) -> float:
    """
    Section 7A: probability that a chosen mate accepts the male's advances.

    The chance is based on the male's intelligence. Average intelligence (10)
    gives a 50% success rate. Clamped to [0.1, 0.95] so even an idiot has
    some chance and a genius isn't guaranteed.
    """
    return max(0.1, min(0.95, float(intelligence) / 20.0))


async def get_breeding_chance(pooch_id: int) -> float:
    """The chance a pooch (as the male) mates with the chosen partner, from its effective intelligence."""
    intelligence = await get_effective_stat(pooch_id, "intelligence")
    return compute_breeding_chance(intelligence if intelligence is not None else 10)


async def select_actual_mate(
    male: object,
    intended_female: object,
    eligible_females: list,
    *,
    rng: random.Random,
    chance: Optional[float] = None,
) -> object:
    """
    Decide whether the intended female actually mates with the male.

    Returns the chosen female pooch. If the intelligence roll fails AND there
    is more than one eligible female in the kennel, picks a random other one.
    With only one eligible female (the intended one), success is guaranteed.
    ``chance`` defaults to one from the male's own intelligence field; callers pass ``get_breeding_chance``.
    """
    if len(eligible_females) <= 1:
        return intended_female
    if chance is None:
        chance = compute_breeding_chance(int(getattr(male, "intelligence", 10) or 10))
    if rng.random() < chance:
        return intended_female
    others = [f for f in eligible_females if f.id != intended_female.id]
    if not others:
        return intended_female
    return rng.choice(others)


@dataclass
class BreedingOutcome:
    """What happened when an owner bred two of their pooches."""

    puppy_ids: list[int]
    disease_events: list[tuple[int, str, str]]
    male: Any
    female: Any
    intended_female: Any

    @property
    def distracted(self) -> bool:
        """True if the male mated with a different female than the one chosen."""
        return self.female.id != self.intended_female.id


async def breed_with_mate_choice(
    owner_discord_id: int,
    first_pooch_id: int,
    second_pooch_id: int,
    rng_seed: Optional[int] = None,
) -> BreedingOutcome:
    """
    Breed two of the owner's pooches. The male may get distracted (see ``select_actual_mate``) and mate with another
    female in his kennel that is ready to breed instead of the chosen one.

    Raises
    ------
    PoochNotFound
        When one of the pooch IDs doesn't link to a real pooch.

    ValueError
        When the owner doesn't own both pooches, or the pair can't breed (see ``breed_pooches``).
    """

    first = await get_pooch_by_id(first_pooch_id)
    second = await get_pooch_by_id(second_pooch_id)
    if first is None:
        raise PoochNotFound(first_pooch_id)
    if second is None:
        raise PoochNotFound(second_pooch_id)
    if first.owner_discord_id != owner_discord_id or second.owner_discord_id != owner_discord_id:
        raise ValueError("That's not your pooch.")
    if first.sex == second.sex:
        raise ValueError("Pooches must be different sexes to breed.")

    male, intended_female = (first, second) if first.sex == "male" else (second, first)

    eligible_females = [intended_female]
    kennel = await get_pooch_kennel(male.id)
    if kennel is not None:
        eligible_females += [
            p
            for p in await list_pooches_for_kennel(kennel.id)
            if p.id != intended_female.id
            and p.sex != male.sex
            and p.alive
            and p.owner_discord_id == owner_discord_id
            and p.breeding_cooldown == 0
            and getattr(p, "pregnancy_timer", None) is None
        ]

    rng = random.Random(rng_seed)
    chance = await get_breeding_chance(male.id)
    female = await select_actual_mate(male, intended_female, eligible_females, rng=rng, chance=chance)
    puppy_ids, disease_events = await breed_pooches(male.id, female.id, rng_seed=rng_seed, return_disease_events=True)
    return BreedingOutcome(
        puppy_ids=puppy_ids,
        disease_events=disease_events,
        male=male,
        female=female,
        intended_female=intended_female,
    )


def describe_breeding_outcome(outcome: BreedingOutcome) -> tuple[str, list[str]]:
    """
    Return the player-facing breeding message and one line per disease event, as both the bot and web show them.

    The puppies are fetuses until they are born, so only their count is reported.
    """

    male, female = outcome.male.name, outcome.female.name
    puppy_count = len(outcome.puppy_ids)
    if puppy_count == 1:
        message = f"**Breeding successful.** {male} and {female} are expecting **1** puppy."
    elif puppy_count == 2:
        message = f"**Twins!** {male} and {female} are expecting **2** puppies."
    else:
        message = f"**Triplets!** {male} and {female} are expecting **{puppy_count}** puppies."
    if outcome.distracted:
        message = f"**{male} got distracted** and ended up mating with **{female}** instead!\n{message}"

    disease_lines = []
    for pooch_id, public_label, event_type in outcome.disease_events:
        if event_type == "spread":
            name = male if pooch_id == outcome.male.id else female if pooch_id == outcome.female.id else "A puppy"
            disease_lines.append(f"{name} was exposed to {public_label}.")
        elif event_type == "inherited":
            disease_lines.append(f"A puppy inherited {public_label}.")
    return message, disease_lines


async def neuter_pooch(owner_discord_id: int, pooch_id: int) -> tuple[bool, str]:
    """
    Neuter one of the owner's pooches at the vet: charge NEUTER_COST and apply the 'Neutered' injury.

    Ownership, life and not-already-neutered are checked before any money is taken.
    """
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found."
    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return False, "Pooch not found."
    if pooch.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch."
    if not pooch.alive:
        return False, "That pooch is already dead."

    existing_injuries = await list_pooch_injuries(pooch_id)
    if any((getattr(i, "name", "") or "").lower() == "neutered" for i in existing_injuries):
        return False, f"{pooch.name} is already neutered."

    injury = await get_injury_by_name("Neutered")
    if injury is None:
        return False, "The vet doesn't have the right tools today (Neutered injury not loaded)."

    if owner.dollars < NEUTER_COST:
        return False, f"Not enough money. Neutering costs **${NEUTER_COST}**."

    await give_money_to_owner(owner_discord_id, -NEUTER_COST)
    await add_injury_to_pooch(pooch_id, injury.id)
    return True, f"{pooch.name} has been neutered. Charged **${NEUTER_COST}**."


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
