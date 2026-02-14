from dataclasses import dataclass
from typing import Optional

from database import get_server_by_discord_id

from database.models import Vendor as VendorORM

from .server import Server, to_server


@dataclass(frozen=True)
class Vendor:
    id: int
    server_discord_id: int
    name: str

    server: Optional[Server]


async def to_vendor(vendor: VendorORM) -> Vendor:
    return Vendor(
        id=vendor.id,
        server_discord_id=vendor.server_discord_id,
        name=vendor.name,
        server=(
            (await to_server(await get_server_by_discord_id(vendor.server_discord_id)))
            if vendor.server_discord_id is not None
            else None
        ),
    )
