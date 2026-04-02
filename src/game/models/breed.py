from dataclasses import dataclass, field

from database.models import Breed as BreedORM


@dataclass(frozen=True)
class Breed:
    id: int

    name: str
    alt_name: str
    category: str
    description: str

    rarity: str

    advanced_options: dict = field(default_factory=dict)


async def to_breed(breed: BreedORM) -> Breed:
    return Breed(
        id=breed.id,
        name=breed.name,
        alt_name=breed.alt_name,
        category=breed.category,
        description=breed.description,
        rarity=breed.rarity,
        advanced_options=breed.advanced_options or {},
    )
