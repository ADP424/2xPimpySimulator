from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.database.models import AuctionBountyListing as AuctionBountyListingORM
    from src.database.models import AuctionSaleListing as AuctionSaleListingORM

    from .pooch import Pooch


@dataclass(frozen=True)
class AuctionSaleListing:
    id: int
    pooch: Pooch
    seller_discord_id: int
    server_discord_id: int
    minimum_bid: int
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    highest_bid: Optional[int]
    highest_bidder_discord_id: Optional[int]
    bid_count: int


@dataclass(frozen=True)
class AuctionBountyListing:
    id: int
    buyer_discord_id: int
    server_discord_id: int
    title: str
    escrow_amount: int
    criteria: list
    created_at: datetime
    is_active: bool


@dataclass(frozen=True)
class BountyMatchResult:
    listing_id: int
    # Each element: {"type": ..., "dollar_value": ..., "matched": bool, ...}
    matched_criteria: list
    payout: int


async def to_auction_sale_listing(
    orm: "AuctionSaleListingORM",
    highest_bid: Optional[int] = None,
    highest_bidder_discord_id: Optional[int] = None,
    bid_count: int = 0,
) -> AuctionSaleListing:
    from src.database import get_pooch_by_id

    from .pooch import to_pooch

    pooch_orm = await get_pooch_by_id(orm.pooch_id)
    pooch = await to_pooch(pooch_orm)
    return AuctionSaleListing(
        id=orm.id,
        pooch=pooch,
        seller_discord_id=orm.seller_discord_id,
        server_discord_id=orm.server_discord_id,
        minimum_bid=orm.minimum_bid,
        created_at=orm.created_at,
        expires_at=orm.expires_at,
        is_active=orm.is_active,
        highest_bid=highest_bid,
        highest_bidder_discord_id=highest_bidder_discord_id,
        bid_count=bid_count,
    )


def to_auction_bounty_listing(orm: "AuctionBountyListingORM") -> AuctionBountyListing:
    return AuctionBountyListing(
        id=orm.id,
        buyer_discord_id=orm.buyer_discord_id,
        server_discord_id=orm.server_discord_id,
        title=orm.title,
        escrow_amount=orm.escrow_amount,
        criteria=list(orm.criteria or []),
        created_at=orm.created_at,
        is_active=orm.is_active,
    )
