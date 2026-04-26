from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.database import (
    get_server_by_discord_id,
    list_vendor_desired_breeds,
    list_vendor_desired_mutations,
    list_vendor_pooch_stock,
)

from .breed import to_breed
from .mutation import to_mutation
from .server import to_server

if TYPE_CHECKING:
    from src.database.models import Vendor as VendorORM

    from .breed import Breed
    from .mutation import Mutation
    from .server import Server


@dataclass(frozen=True)
class Vendor:
    id: int
    server_discord_id: int

    name: str
    price_markup: float
    stock_count: int

    desired_mutations: list[Mutation]
    desired_breeds: list[Breed]

    server: Server | None


async def to_vendor(vendor: VendorORM) -> Vendor:
    """
    Convert an ORM Vendor object to a game Vendor object.

    Parameters
    ----------
    vendor: Vendor
        The Vendor object to convert.

    Returns
    -------
    Vendor
        The converted Vendor dataclass object.
    """

    desired_mutation_orms = await list_vendor_desired_mutations(vendor.id)
    desired_breed_orms = await list_vendor_desired_breeds(vendor.id)

    return Vendor(
        id=vendor.id,
        server_discord_id=vendor.server_discord_id,
        name=vendor.name,
        price_markup=vendor.price_markup,
        stock_count=len(await list_vendor_pooch_stock(vendor.id)),
        desired_mutations=[await to_mutation(m) for m in desired_mutation_orms],
        desired_breeds=[await to_breed(b) for b in desired_breed_orms],
        server=(
            (await to_server(await get_server_by_discord_id(vendor.server_discord_id)))
            if vendor.server_discord_id is not None
            else None
        ),
    )
