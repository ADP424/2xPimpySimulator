from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.database import get_breed_by_id as db_get_breed_by_id
from src.database import get_disease_by_id as db_get_disease_by_id
from src.database import get_injury_by_id as db_get_injury_by_id
from src.database import get_mutation_by_id as db_get_mutation_by_id
from src.database import list_all_breeds as db_list_all_breeds
from src.database import list_all_diseases as db_list_all_diseases
from src.database import list_all_injuries as db_list_all_injuries
from src.database import list_all_mutations as db_list_all_mutations
from src.database.models import Injury

from .models import to_breed, to_disease, to_mutation

if TYPE_CHECKING:
    from .models import Breed, Disease, Mutation


async def get_breed_by_id(breed_id: int) -> Optional[Breed]:
    """
    Return the breed with the given ID, if it exists.

    Parameters
    ----------
    breed_id: int
        The ID of the breed to fetch.

    Returns
    -------
    Breed, optional
        The Breed object, or None if no breed was found.
    """

    breed = await db_get_breed_by_id(breed_id)
    if breed is None:
        return None
    return await to_breed(breed)


async def get_mutation_by_id(mutation_id: int) -> Optional[Mutation]:
    """
    Return the mutation with the given ID, if it exists.

    Parameters
    ----------
    mutation_id: int
        The ID of the mutation to fetch.

    Returns
    -------
    Mutation, optional
        The Mutation object, or None if no mutation was found.
    """

    mutation = await db_get_mutation_by_id(mutation_id)
    if mutation is None:
        return None
    return await to_mutation(mutation)


async def list_all_breeds() -> list[Breed]:
    """
    Fetches a list of all possible breeds a pooch can be.

    Returns
    -------
    list[Breed]
        The list of every breed in the game.
    """

    breeds = await db_list_all_breeds()
    return [(await to_breed(breed)) for breed in breeds]


async def list_all_mutations() -> list[Mutation]:
    """
    Fetches a list of all possible mutations a pooch can get.

    Returns
    -------
    list[Mutation]
        The list of every mutation in the game.
    """

    mutations = await db_list_all_mutations()
    return [(await to_mutation(mutation)) for mutation in mutations]


async def get_injury_by_id(injury_id: int) -> Optional[Injury]:
    """Return the Injury ORM object with the given ID, or None."""
    return await db_get_injury_by_id(injury_id)


async def list_all_injuries() -> list[Injury]:
    """
    Fetches a list of all possible injuries a pooch can get.

    Returns
    -------
    list[Injury]
        The list of every injury in the game.
    """

    return await db_list_all_injuries()


async def get_disease_by_id(disease_id: int) -> Optional[Disease]:
    """Return the disease with the given ID, if it exists.

    Parameters
    ----------
    disease_id: int
        The ID of the disease to fetch.

    Returns
    -------
    Disease, optional
        The Disease object, or None if no disease was found.
    """

    disease = await db_get_disease_by_id(disease_id)
    if disease is None:
        return None
    return await to_disease(disease)


async def list_all_diseases(season: str | None = None) -> list[Disease]:
    """Fetches a list of all possible diseases a pooch can get.

    Parameters
    ----------
    season: str, optional
        When provided, only diseases available in that season are returned.

    Returns
    -------
    list[Disease]
        The list of every disease in the game.
    """

    diseases = await db_list_all_diseases(season=season)
    return [(await to_disease(d)) for d in diseases]
