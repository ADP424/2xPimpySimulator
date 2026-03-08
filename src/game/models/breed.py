from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    """
    Convert an ORM Breed object to a game Breed object.

    Parameters
    ----------
    breed: Breed
        The Breed object to convert.

    Returns
    -------
    Breed
        The converted Breed dataclass object.
    """

    return Breed(
        id=breed.id,
        name=breed.name,
        alt_name=breed.alt_name,
        category=breed.category,
        description=breed.description,
        rarity=breed.rarity,
    )
