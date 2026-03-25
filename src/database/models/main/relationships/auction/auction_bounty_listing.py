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
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .... import Base

if TYPE_CHECKING:
    from ...entities import Owner, Pooch, Server


class AuctionBountyListing(Base):
    __tablename__ = "auction_bounty_listings"
    __table_args__ = (
        CheckConstraint("escrow_amount > 0", name="auction_bounty_positive_escrow"),
        Index(
            "idx_bounty_listings_server",
            "server_discord_id",
            postgresql_where="is_active = TRUE",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    buyer_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"), nullable=False
    )
    server_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.discord_id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Amount deducted from buyer on creation; held until fulfilled or cancelled.
    # Payout = min(sum of matched criterion dollar_values, escrow_amount).
    escrow_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    # List of criterion dicts; see Documentation/Auction House Guide for schema.
    criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    fulfilled_by_discord_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="SET NULL"), nullable=True
    )
    fulfilled_pooch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pooches.id", ondelete="SET NULL"), nullable=True
    )

    buyer: Mapped["Owner"] = relationship("Owner", foreign_keys=[buyer_discord_id])
    server: Mapped["Server"] = relationship("Server", foreign_keys=[server_discord_id])
    fulfilled_by: Mapped["Owner | None"] = relationship("Owner", foreign_keys=[fulfilled_by_discord_id])
    fulfilled_pooch: Mapped["Pooch | None"] = relationship("Pooch", foreign_keys=[fulfilled_pooch_id])
