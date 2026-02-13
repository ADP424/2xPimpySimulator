from dataclasses import dataclass

from database.models import Vendor as VendorORM


@dataclass(frozen=True)
class Vendor:
    id: int
    server_discord_id: int
    name: str


def to_vendor(vendor: VendorORM) -> Vendor:
    return Vendor(
        id=int(getattr(vendor, "id")),
        server_discord_id=int(getattr(vendor, "server_discord_id")),
        name=str(getattr(vendor, "name")),
    )
