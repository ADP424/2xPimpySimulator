from database import list_all_breeds as db_list_all_breeds
from database import list_all_mutations as db_list_all_mutations

from .models import Breed, Mutation, to_breed, to_mutation


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
