from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.database.models import Mutation as MutationORM


@dataclass(frozen=True)
class Mutation:
    id: int

    name: str
    alt_name: str
    category: str
    description: str

    heritability: float

    health_impact: str
    rarity: str

    affects_females: bool
    affects_males: bool

    parameters: dict = field(default_factory=dict)

    visible: bool = True
    invisible_messages: Optional[list[str]] = None
    reveal_chance: float = 1.0


async def to_mutation(mutation: MutationORM) -> Mutation:
    """
    Convert an ORM Mutation object to a game Mutation object.

    Parameters
    ----------
    mutation: Mutation
        The Mutation object to convert.

    Returns
    -------
    Mutation
        The converted Mutation dataclass object.
    """

    return Mutation(
        id=mutation.id,
        name=mutation.name,
        alt_name=mutation.alt_name,
        category=mutation.category,
        description=mutation.description,
        heritability=mutation.heritability,
        health_impact=mutation.health_impact,
        rarity=mutation.rarity,
        affects_females=mutation.affects_females,
        affects_males=mutation.affects_males,
        parameters=mutation.parameters or {},
        visible=mutation.visible,
        invisible_messages=mutation.invisible_messages,
        reveal_chance=mutation.reveal_chance,
    )
