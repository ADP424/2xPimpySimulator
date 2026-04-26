from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .... import Base

if TYPE_CHECKING:
    from ...entities import Owner, Pooch, Server
    from .auction_bid import AuctionBid


class AuctionSaleListing(Base):
    __tablename__ = "auction_sale_listings"
    __table_args__ = (
        CheckConstraint("minimum_bid >= 0", name="auction_sale_minimum_bid"),
        # Only one active listing per pooch at a time
        Index(
            "uq_auction_sale_pooch_active",
            "pooch_id",
            unique=True,
            postgresql_where="is_active = TRUE",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), nullable=False)
    seller_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"), nullable=False
    )
    server_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.discord_id", ondelete="CASCADE"), nullable=False
    )

    minimum_bid: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    winning_bidder_discord_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="SET NULL"), nullable=True
    )
    winning_bid_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pooch: Mapped["Pooch"] = relationship("Pooch", foreign_keys=[pooch_id])
    seller: Mapped["Owner"] = relationship("Owner", foreign_keys=[seller_discord_id])
    server: Mapped["Server"] = relationship("Server", foreign_keys=[server_discord_id])
    winning_bidder: Mapped["Owner | None"] = relationship("Owner", foreign_keys=[winning_bidder_discord_id])
    bids: Mapped[list["AuctionBid"]] = relationship(
        "AuctionBid", back_populates="listing", cascade="all, delete-orphan"
    )
