from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from src.database import (
    get_owner_by_discord_id,
    get_vendor_by_id,
    list_pooch_breeds,
    list_pooch_disease_instances,
    list_pooch_injury_instances,
    list_pooch_mutation_instances,
    list_pooch_mutations,
)

from ..constants import (
    BREEDING_COOLDOWN_HEATING_UP_THRESHOLD,
    POOCH_OLD_AGE,
    POOCH_SICK_HEALTH,
)
from ..manage_stats import compute_effective_stats, get_pooch_health
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

    # Hourly-tick state (lots-of-changes columns). Defaults only so test factories needn't pass them; to_pooch
    # always copies them from the row.
    pregnancy_timer: Optional[int] = None
    rejuvenation_count: int = 0
    immortal: bool = False
    starvation: int = 0
    birth_hour: Optional[int] = None
    mess_output: int = 2
    consumption: int = 1

    @property
    def birthday(self) -> Optional[datetime]:
        if self.created_at is None:
            return None
        return self.created_at - timedelta(days=max(0, self.age))

    @property
    def status(self) -> str:
        return get_pooch_status(self.alive, self.age, self.health)

    @property
    def breeding_status(self) -> str:
        return get_breeding_status(self.breeding_cooldown)

    @property
    def can_breed(self) -> bool:
        return self.alive and self.breeding_cooldown == 0 and self.pregnancy_timer is None


def get_pooch_status(alive: bool, age: int, health: int) -> str:
    """Return "dead", "old", "sick" or "healthy"."""
    if not alive:
        return "dead"
    if age >= POOCH_OLD_AGE:
        return "old"
    if health <= POOCH_SICK_HEALTH:
        return "sick"
    return "healthy"


def get_breeding_status(cooldown: int) -> str:
    """Return "in_heat", "heating_up" or "cooled" for a breeding cooldown."""
    if cooldown == 0:
        return "in_heat"
    if cooldown <= BREEDING_COOLDOWN_HEATING_UP_THRESHOLD:
        return "heating_up"
    return "cooled"


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

    stats = compute_effective_stats(
        pooch, mutations=mutation_orms, breeds=breed_pairs, injuries=injury_instances, diseases=disease_instances
    )

    return Pooch(
        id=pooch.id,
        name=pooch.name,
        age=pooch.age,
        sex=pooch.sex,
        base_health=stats["base_health"],
        health_loss_age=pooch.health_loss_age,
        strength=stats["strength"],
        cuteness=stats["cuteness"],
        fluffiness=stats["fluffiness"],
        intelligence=stats["intelligence"],
        dexterity=stats["dexterity"],
        fertility=stats["fertility"],
        aggressiveness=stats["aggressiveness"],
        constitution=stats["constitution"],
        size=stats["size"],
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
        pregnancy_timer=pooch.pregnancy_timer,
        rejuvenation_count=pooch.rejuvenation_count or 0,
        immortal=bool(pooch.immortal),
        starvation=pooch.starvation or 0,
        birth_hour=pooch.birth_hour,
        mess_output=pooch.mess_output,
        consumption=pooch.consumption,
    )
