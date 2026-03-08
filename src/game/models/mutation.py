from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models import Mutation as MutationORM


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
    )
