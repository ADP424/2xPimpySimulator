from database import (
    list_vendors as db_list_vendors,
    list_vendor_pooch_stock as list_vendor_pooch_stock_orm,
    purchase_vendor_pooch,
)

from .model import Vendor, to_vendor, Pooch, to_pooch


def get_price(pooch_id: int) -> int:
    # TODO: real pricing logic
    return 50


async def list_server_vendors(server_id: int) -> list[Vendor]:
    vendors = await db_list_vendors(server_id)
    return [to_vendor(v) for v in vendors]


async def list_vendor_pooches(server_id: int, vendor_id: int) -> list[Pooch]:
    pooches = await list_vendor_pooch_stock_orm(server_id, vendor_id)
    return [to_pooch(p) for p in pooches]


async def buy_pooch(
    *,
    server_id: int,
    owner_discord_id: int,
    vendor_id: int,
    pooch_id: int,
) -> tuple[bool, str]:
    price = get_price(pooch_id)
    return await purchase_vendor_pooch(
        server_id=server_id,
        owner_discord_id=owner_discord_id,
        vendor_id=vendor_id,
        pooch_id=pooch_id,
        price=price,
    )
