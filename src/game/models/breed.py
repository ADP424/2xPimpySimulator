from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import Breed as BreedORM


@dataclass(frozen=True)
class Breed:
    id: int

    name: str
    alt_name: str
    category: str
    description: str

    rarity: str
    min_size: int
    max_size: int

    parameters: dict = field(default_factory=dict)


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
        min_size=breed.min_size,
        max_size=breed.max_size,
        parameters=breed.parameters or {},
    )
