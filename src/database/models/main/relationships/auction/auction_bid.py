from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .... import Base

if TYPE_CHECKING:
    from ...entities import Owner
    from .auction_sale_listing import AuctionSaleListing


class AuctionBid(Base):
    __tablename__ = "auction_bids"
    __table_args__ = (
        CheckConstraint("amount > 0", name="auction_bid_positive_amount"),
        Index("idx_auction_bids_listing", "listing_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auction_sale_listings.id", ondelete="CASCADE"), nullable=False
    )
    bidder_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"), nullable=False
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    listing: Mapped["AuctionSaleListing"] = relationship("AuctionSaleListing", back_populates="bids")
    bidder: Mapped["Owner"] = relationship("Owner", foreign_keys=[bidder_discord_id])
