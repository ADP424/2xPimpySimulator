from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from src.database import (
    get_owner_by_discord_id,
    get_pooch_health,
    get_vendor_by_id,
    list_pooch_breeds,
    list_pooch_injuries,
    list_pooch_mutations,
)

from .breed import to_breed
from .mutation import to_mutation
from .owner import to_owner
from .vendor import to_vendor

if TYPE_CHECKING:
    from src.database.models import Injury
    from src.database.models import Pooch as PoochORM

    from .breed import Breed
    from .mutation import Mutation
    from .owner import Owner
    from .vendor import Vendor


@dataclass(frozen=True)
class PoochBreedInfo:
    breed: Breed
    relative_weight: float


@dataclass(frozen=True)
class Pooch:
    id: int

    name: str
    age: int
    sex: str

    base_health: int
    health_loss_age: int

    strength: int
    cuteness: int
    fluffiness: int
    intelligence: int
    dexterity: int
    fertility: int
    aggressiveness: int
    constitution: int

    breeding_cooldown: int
    alive: bool
    virgin: bool
    mood: Optional[str]

    owner_discord_id: Optional[int]
    vendor_id: Optional[int]

    created_at: Optional[datetime]

    size: int

    health: int

    owner: Optional[Owner]
    vendor: Optional[Vendor]

    breeds: list[PoochBreedInfo]
    mutations: list[Mutation]
    injuries: list[Injury]

    @property
    def birthday(self) -> Optional[datetime]:
        return self.created_at

    @property
    def status(self) -> str:
        if not self.alive:
            return "dead"
        elif self.age >= 12:
            return "old"
        elif self.health <= 5:
            return "sick"
        return "healthy"


def _apply_stat_params(base: int, stat: str, mutation_orms: list, breed_pairs: list, injury_orms: list) -> int:
    """Apply _add and _mult parameters from mutations, breeds, and injuries to a base stat value."""
    total = float(base)

    # Mutations: flat add then mult
    mut_add = sum(m.parameters.get(f"{stat}_add", 0) for m in mutation_orms)
    mut_mult = 1.0
    for m in mutation_orms:
        mut_mult *= m.parameters.get(f"{stat}_mult", 1.0)
    total = (total + mut_add) * mut_mult

    # Breeds: weighted add and weighted-average mult
    total_weight = sum(rel for _, rel in breed_pairs)
    if total_weight > 0:
        breed_add = sum(b.parameters.get(f"{stat}_add", 0) * (rel / total_weight) for b, rel in breed_pairs)
        breed_mult = sum(b.parameters.get(f"{stat}_mult", 1.0) * (rel / total_weight) for b, rel in breed_pairs)
        total = (total + breed_add) * breed_mult

    # Injuries: per-instance flat add then mult, then stack effects
    inj_add = sum(i.parameters.get(f"{stat}_add", 0) for i in injury_orms)
    inj_mult = 1.0
    for i in injury_orms:
        inj_mult *= i.parameters.get(f"{stat}_mult", 1.0)
    total = (total + inj_add) * inj_mult

    # Stack effects: group injuries by id, apply entries whose count threshold is met
    injury_counts: dict[int, tuple[Any, int]] = {}
    for i in injury_orms:
        if i.id not in injury_counts:
            injury_counts[i.id] = (i, 0)
        injury_counts[i.id] = (i, injury_counts[i.id][1] + 1)

    stack_add = 0.0
    stack_mult = 1.0
    for injury, count in injury_counts.values():
        for entry in (injury.parameters or {}).get("stacks", []):
            min_count = entry.get("min_count", 1)
            max_count = entry.get("max_count")
            if count >= min_count and (max_count is None or count <= max_count):
                stack_add += entry.get(f"{stat}_add", 0)
                stack_mult *= entry.get(f"{stat}_mult", 1.0)
    total = (total + stack_add) * stack_mult

    return round(total)


async def to_pooch(pooch: PoochORM) -> Pooch:
    """
    Convert an ORM Pooch object to a game Pooch object.

    Parameters
    ----------
    pooch: Pooch
        The Pooch object to convert.

    Returns
    -------
    Pooch
        The converted Pooch dataclass object.
    """

    breed_pairs = await list_pooch_breeds(pooch.id)
    breeds = [PoochBreedInfo(breed=(await to_breed(b)), relative_weight=rel) for b, rel in breed_pairs]

    mutation_orms = await list_pooch_mutations(pooch.id)
    mutations = [(await to_mutation(m)) for m in mutation_orms]

    injury_orms = await list_pooch_injuries(pooch.id)

    return Pooch(
        id=pooch.id,
        name=pooch.name,
        age=pooch.age,
        sex=pooch.sex,
        base_health=_apply_stat_params(pooch.base_health, "base_health", mutation_orms, breed_pairs, injury_orms),
        health_loss_age=pooch.health_loss_age,
        strength=_apply_stat_params(pooch.strength, "strength", mutation_orms, breed_pairs, injury_orms),
        cuteness=_apply_stat_params(pooch.cuteness, "cuteness", mutation_orms, breed_pairs, injury_orms),
        fluffiness=_apply_stat_params(pooch.fluffiness, "fluffiness", mutation_orms, breed_pairs, injury_orms),
        intelligence=_apply_stat_params(pooch.intelligence, "intelligence", mutation_orms, breed_pairs, injury_orms),
        dexterity=_apply_stat_params(pooch.dexterity, "dexterity", mutation_orms, breed_pairs, injury_orms),
        fertility=_apply_stat_params(pooch.fertility, "fertility", mutation_orms, breed_pairs, injury_orms),
        aggressiveness=_apply_stat_params(
            pooch.aggressiveness, "aggressiveness", mutation_orms, breed_pairs, injury_orms
        ),
        constitution=_apply_stat_params(pooch.constitution, "constitution", mutation_orms, breed_pairs, injury_orms),
        size=_apply_stat_params(pooch.size, "size", mutation_orms, breed_pairs, injury_orms),
        breeding_cooldown=pooch.breeding_cooldown,
        alive=pooch.alive,
        virgin=pooch.virgin,
        mood=pooch.mood,
        health=(await get_pooch_health(pooch.id)),
        owner_discord_id=pooch.owner_discord_id,
        vendor_id=pooch.vendor_id,
        created_at=pooch.created_at,
        owner=(
            (await to_owner(await get_owner_by_discord_id(pooch.owner_discord_id)))
            if pooch.owner_discord_id is not None
            else None
        ),
        vendor=(await to_vendor(await get_vendor_by_id(pooch.vendor_id))) if pooch.vendor_id is not None else None,
        breeds=breeds,
        mutations=mutations,
        injuries=injury_orms,
    )
