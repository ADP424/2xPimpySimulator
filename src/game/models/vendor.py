from dataclasses import dataclass
from typing import Optional

from database import get_mutation_by_id, get_server_by_discord_id
from database.models import Vendor as VendorORM

from .mutation import Mutation, to_mutation
from .server import Server, to_server


@dataclass(frozen=True)
class Vendor:
    id: int
    server_discord_id: int

    name: str
    price_markup: float

    desired_mutation_1: Optional[Mutation]
    desired_mutation_2: Optional[Mutation]
    desired_mutation_3: Optional[Mutation]

    server: Optional[Server]


async def to_vendor(vendor: VendorORM) -> Vendor:
    return Vendor(
        id=vendor.id,
        server_discord_id=vendor.server_discord_id,
        name=vendor.name,
        price_markup=vendor.price_markup,
        desired_mutation_1=(
            await to_mutation(await get_mutation_by_id(vendor.desired_mutation_1))
            if vendor.desired_mutation_1 is not None
            else None
        ),
        desired_mutation_2=(
            await to_mutation(await get_mutation_by_id(vendor.desired_mutation_2))
            if vendor.desired_mutation_2 is not None
            else None
        ),
        desired_mutation_3=(
            await to_mutation(await get_mutation_by_id(vendor.desired_mutation_3))
            if vendor.desired_mutation_3 is not None
            else None
        ),
        server=(
            (await to_server(await get_server_by_discord_id(vendor.server_discord_id)))
            if vendor.server_discord_id is not None
            else None
        ),
    )
