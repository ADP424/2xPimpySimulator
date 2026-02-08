import asyncio
import json
from typing import Any

from database.models import Breed, Mutation, DogName, VendorFirstName, VendorLastName
from database.session import session_scope
from sqlalchemy import delete, func, select


async def load_breeds():
    with open("resources/breeds.json", "r") as breeds_json_file:
        breeds_json: dict[str, dict[str, dict[str, str | Any]]] = json.loads(breeds_json_file.read().strip())

    async with session_scope() as session:

        # delete
        await session.execute(delete(Breed))

        # load
        for breed_category, breeds in breeds_json.items():
            for breed, attributes in breeds.items():
                session.add(
                    Breed(
                        name=str(breed),
                        alt_name=str(attributes.get("alt_name", str(breed))),
                        category=str(breed_category),
                        description=str(attributes.get("description", f"{str(breed).capitalize()} is a type of dog.")),
                        rarity=str(attributes.get("rarity", "common")).lower(),
                    )
                )


async def load_mutations():
    with open("resources/mutations.json", "r") as mutations_json_file:
        mutations_json: dict[str, dict[str, dict[str, str | Any]]] = json.loads(mutations_json_file.read().strip())

    async with session_scope() as session:

        # delete
        await session.execute(delete(Mutation))

        # load
        for mutation_category, mutations in mutations_json.items():
            for mutation, attributes in mutations.items():
                session.add(
                    Mutation(
                        name=str(mutation),
                        alt_name=str(attributes.get("alt_name", str(mutation))),
                        category=str(mutation_category),
                        description=str(attributes.get("description", f"{str(mutation).capitalize()} is a mutation for dogs.")),
                        heritability=float(attributes.get("heritability", 25.0)),
                        health_impact=str(attributes.get("health_impact", "neutral")).lower(),
                        rarity=str(attributes.get("rarity", "common")).lower(),
                        affects_males=bool(attributes.get("affects_males", True)),
                        affects_females=bool(attributes.get("affects_females", True)),
                        advanced_options=attributes.get("advanced_options", {}),
                    )
                )


async def load_dog_names():
    with open("resources/dog_names.txt", "r") as dog_names_file:
        dog_names = dog_names_file.readlines()

    async with session_scope() as session:

        # delete
        await session.execute(delete(DogName))

        # load
        for dog_name in dog_names:
            dog_name = dog_name.strip()
            if dog_name:
                session.add(DogName(name=dog_name))


async def load_vendor_first_names():
    with open("resources/vendor_first_names.txt", "r") as vendor_first_names_file:
        vendor_first_names = vendor_first_names_file.readlines()

    async with session_scope() as session:

        # delete
        await session.execute(delete(VendorFirstName))

        # load
        for vendor_first_name in vendor_first_names:
            vendor_first_name = vendor_first_name.strip()
            if vendor_first_name:
                session.add(VendorFirstName(name=vendor_first_name))


async def load_vendor_last_names():
    with open("resources/vendor_last_names.txt", "r") as vendor_last_names_file:
        vendor_last_names = vendor_last_names_file.readlines()

    async with session_scope() as session:

        # delete
        await session.execute(delete(VendorLastName))

        # load
        for vendor_last_name in vendor_last_names:
            vendor_last_name = vendor_last_name.strip()
            if vendor_last_name:
                session.add(VendorLastName(name=vendor_last_name))


async def main():
    await load_breeds()
    await load_mutations()
    await load_dog_names()
    await load_vendor_first_names()
    await load_vendor_last_names()


if __name__ == "__main__":
    asyncio.run(main())
