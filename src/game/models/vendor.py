from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from src.database import (
    get_mutation_by_id,
    get_server_by_discord_id,
    list_vendor_pooch_stock,
)

from .mutation import to_mutation
from .server import to_server

if TYPE_CHECKING:
    from src.database.models import Vendor as VendorORM

    from .mutation import Mutation
    from .server import Server


@dataclass(frozen=True)
class Vendor:
    id: int
    server_discord_id: int

    name: str
    price_markup: float
    stock_count: int

    desired_mutation_1: Optional[Mutation]
    desired_mutation_2: Optional[Mutation]
    desired_mutation_3: Optional[Mutation]

    server: Optional[Server]


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

    return Vendor(
        id=vendor.id,
        server_discord_id=vendor.server_discord_id,
        name=vendor.name,
        price_markup=vendor.price_markup,
        stock_count=len(await list_vendor_pooch_stock(vendor.id)),
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
