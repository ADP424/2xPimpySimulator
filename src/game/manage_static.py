from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from database import get_breed_by_id as db_get_breed_by_id
from database import get_mutation_by_id as db_get_mutation_by_id
from database import list_all_breeds as db_list_all_breeds
from database import list_all_mutations as db_list_all_mutations

from .models import to_breed, to_mutation

if TYPE_CHECKING:
    from .models import Breed, Mutation


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
