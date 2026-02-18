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


@dataclass(frozen=True)
class PoochBreedInfo:
    breed: Breed
    relative_weight: float


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


async def to_pooch_breed_info(breed: BreedORM, relative_weight: float) -> PoochBreedInfo:
    """
    Return an object that holds a specific pooch's breed and its relative weight on that pooch.

    Parameters
    ----------
    breed: Breed
        The ORM database breed object the pooch has.

    relative_weight: float
        The relative weight of the breed on the pooch.

    Returns
    -------
    PoochBreedInfo
        The breed info object with the pooch's breed and its weight on it.
    """

    return PoochBreedInfo(breed=(await to_breed(breed)), relative_weight=float(relative_weight))
