from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from src.database import (
    get_owner_by_discord_id,
    get_pooch_health,
    get_vendor_by_id,
    list_pooch_breeds,
    list_pooch_disease_instances,
    list_pooch_injury_instances,
    list_pooch_mutation_instances,
    list_pooch_mutations,
)

from ..constants import BREEDING_COOLDOWN_HEATING_UP_THRESHOLD
from .breed import to_breed
from .mutation import to_mutation
from .owner import to_owner
from .vendor import to_vendor

if TYPE_CHECKING:
    from src.database.models import Disease, Injury
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
class PoochMutationInfo:
    mutation: Mutation
    displayed_symptom: Optional[str]
    visible: bool  # per-instance visibility (may be revealed by diagnosis)


@dataclass(frozen=True)
class PoochInjuryInfo:
    injury: Injury
    displayed_symptom: Optional[str]
    visible: bool  # per-instance visibility (may be revealed by diagnosis)


@dataclass(frozen=True)
class PoochDiseaseInfo:
    disease: Disease
    displayed_symptom: Optional[str]
    visible: bool  # per-instance visibility (may be revealed by diagnosis)
    treated: bool


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
    vet_checked: bool
    mood: Optional[str]

    owner_discord_id: Optional[int]
    vendor_id: Optional[int]

    created_at: Optional[datetime]

    size: int

    health: int

    owner: Optional[Owner]
    vendor: Optional[Vendor]

    breeds: list[PoochBreedInfo]
    mutations: list[PoochMutationInfo]
    injuries: list[PoochInjuryInfo]
    diseases: list[PoochDiseaseInfo]

    @property
    def birthday(self) -> Optional[datetime]:
        if self.created_at is None:
            return None
        return self.created_at - timedelta(days=max(0, self.age))

    @property
    def status(self) -> str:
        if not self.alive:
            return "dead"
        elif self.age >= 12:
            return "old"
        elif self.health <= 5:
            return "sick"
        return "healthy"

    @property
    def breeding_status(self) -> str:
        return get_breeding_status(self.breeding_cooldown)

    @property
    def can_breed(self) -> bool:
        return self.alive and self.breeding_cooldown == 0


def get_breeding_status(cooldown: int) -> str:
    """Return "in_heat", "heating_up" or "cooled" for a breeding cooldown."""
    if cooldown == 0:
        return "in_heat"
    if cooldown <= BREEDING_COOLDOWN_HEATING_UP_THRESHOLD:
        return "heating_up"
    return "cooled"


def apply_stat_params(
    base: int,
    stat: str,
    mutation_orms: list,
    breed_pairs: list,
    injury_instances: list,
    disease_instances: list | None = None,
) -> int:
    """Apply _add and _mult parameters from mutations, breeds, injuries, and diseases to a base stat value.

    injury_instances: list of PoochInjury ORM records (each has .injury and .treated).
    disease_instances: list of PoochDisease ORM records (each has .disease).
    """
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

    # Injuries: per-instance flat add then mult from main parameters
    # When an instance is treated and has a 'treated' block with stat params, apply those instead of the main ones.
    inj_add = 0.0
    inj_mult = 1.0
    for pi in injury_instances:
        injury = pi.injury
        params = injury.parameters or {}
        if pi.treated and injury.treated:
            treated_params = injury.treated
            inj_add += treated_params.get(f"{stat}_add", 0)
            inj_mult *= treated_params.get(f"{stat}_mult", params.get(f"{stat}_mult", 1.0))
        else:
            inj_add += params.get(f"{stat}_add", 0)
            inj_mult *= params.get(f"{stat}_mult", 1.0)
    total = (total + inj_add) * inj_mult

    disease_instances = disease_instances or []

    disease_add = 0.0
    disease_mult = 1.0
    for pd in disease_instances:
        params = pd.disease.parameters or {}
        disease_add += params.get(f"{stat}_add", 0)
        disease_mult *= params.get(f"{stat}_mult", 1.0)
    total = (total + disease_add) * disease_mult

    # Stack effects: group injuries by id, apply entries whose count threshold is met
    injury_counts: dict[int, tuple[Any, int]] = {}
    for pi in injury_instances:
        injury = pi.injury
        if injury.id not in injury_counts:
            injury_counts[injury.id] = (injury, 0)
        injury_counts[injury.id] = (injury, injury_counts[injury.id][1] + 1)

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
    mutation_instances = await list_pooch_mutation_instances(pooch.id)
    # Build a map from mutation_id → displayed_symptom for O(1) lookup
    mutation_symptom_map = {pm.mutation_id: pm.displayed_symptom for pm in mutation_instances}
    mutations = [
        PoochMutationInfo(
            mutation=(await to_mutation(m)),
            displayed_symptom=mutation_symptom_map.get(m.id),
            visible=next((pm.visible for pm in mutation_instances if pm.mutation_id == m.id), m.visible),
        )
        for m in mutation_orms
    ]

    injury_instances = await list_pooch_injury_instances(pooch.id)
    injuries = [
        PoochInjuryInfo(injury=pi.injury, displayed_symptom=pi.displayed_symptom, visible=pi.visible)
        for pi in injury_instances
    ]

    disease_instances = await list_pooch_disease_instances(pooch.id)
    diseases = [
        PoochDiseaseInfo(
            disease=pdi.disease,
            displayed_symptom=pdi.displayed_symptom,
            visible=pdi.visible,
            treated=pdi.treated,
        )
        for pdi in disease_instances
    ]

    return Pooch(
        id=pooch.id,
        name=pooch.name,
        age=pooch.age,
        sex=pooch.sex,
        base_health=apply_stat_params(
            pooch.base_health, "base_health", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        health_loss_age=pooch.health_loss_age,
        strength=apply_stat_params(
            pooch.strength, "strength", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        cuteness=apply_stat_params(
            pooch.cuteness, "cuteness", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        fluffiness=apply_stat_params(
            pooch.fluffiness, "fluffiness", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        intelligence=apply_stat_params(
            pooch.intelligence, "intelligence", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        dexterity=apply_stat_params(
            pooch.dexterity, "dexterity", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        fertility=apply_stat_params(
            pooch.fertility, "fertility", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        aggressiveness=apply_stat_params(
            pooch.aggressiveness, "aggressiveness", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        constitution=apply_stat_params(
            pooch.constitution, "constitution", mutation_orms, breed_pairs, injury_instances, disease_instances
        ),
        size=apply_stat_params(pooch.size, "size", mutation_orms, breed_pairs, injury_instances, disease_instances),
        breeding_cooldown=pooch.breeding_cooldown,
        alive=pooch.alive,
        virgin=pooch.virgin,
        vet_checked=pooch.vet_checked,
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
        injuries=injuries,
        diseases=diseases,
    )
