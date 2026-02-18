from database import list_all_breeds as db_list_all_breeds
from database import list_all_mutations as db_list_all_mutations

from .model import Breed, Mutation, to_breed, to_mutation


async def list_all_breeds() -> list[Breed]:
    breeds = await db_list_all_breeds()
    return [(await to_breed(b)) for b in breeds]


async def list_all_mutations() -> list[Mutation]:
    mutations = await db_list_all_mutations()
    return [(await to_mutation(m)) for m in mutations]
