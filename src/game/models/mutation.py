from dataclasses import dataclass, field

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

    advanced_options: dict = field(default_factory=dict)


async def to_mutation(mutation: MutationORM) -> Mutation:
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
        advanced_options=mutation.advanced_options or {},
    )
