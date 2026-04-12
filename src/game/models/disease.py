from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.database.models import Disease as DiseaseORM


@dataclass(frozen=True)
class Disease:
    id: int

    name: str
    category: str
    description: str

    health_impact: str

    contagion_chance: float
    sexually_transmitted: bool

    recovery_chance: float
    treatable: bool
    curable: bool

    immunity_duration: Optional[int]

    heritability: float

    seasons: Optional[list[str]]
    season_contagion_modifiers: Optional[dict]

    parameters: dict = field(default_factory=dict)

    visible: bool = True
    invisible_messages: Optional[list[str]] = None
    reveal_chance: float = 1.0


async def to_disease(disease: DiseaseORM) -> Disease:
    """Convert an ORM Disease object to a game Disease object.

    Parameters
    ----------
    disease: Disease
        The Disease ORM object to convert.

    Returns
    -------
    Disease
        The converted Disease dataclass object.
    """

    return Disease(
        id=disease.id,
        name=disease.name,
        category=disease.category,
        description=disease.description,
        health_impact=disease.health_impact,
        contagion_chance=disease.contagion_chance,
        sexually_transmitted=disease.sexually_transmitted,
        recovery_chance=disease.recovery_chance,
        treatable=disease.treatable,
        curable=disease.curable,
        immunity_duration=disease.immunity_duration,
        heritability=disease.heritability,
        seasons=disease.seasons,
        season_contagion_modifiers=disease.season_contagion_modifiers,
        parameters=disease.parameters or {},
        visible=disease.visible,
        invisible_messages=disease.invisible_messages,
        reveal_chance=disease.reveal_chance,
    )
