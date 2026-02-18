from dataclasses import dataclass

from database.models import Breed as BreedORM


@dataclass(frozen=True)
class Breed:
    id: int

    name: str
    alt_name: str
    category: str
    description: str

    rarity: str


async def to_breed(breed: BreedORM) -> Breed:
    return Breed(
        id=breed.id,
        name=breed.name,
        alt_name=breed.alt_name,
        category=breed.category,
        description=breed.description,
        rarity=breed.rarity,
    )
