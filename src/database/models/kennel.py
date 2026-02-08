from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base

if TYPE_CHECKING:
    from .owner import Owner
    from .relationships.kennel_pooch import KennelPooch


class Kennel(Base):
    __tablename__ = "kennels"
    __table_args__ = (
        UniqueConstraint("server_id", "id", name="kennels_server_id_id_uniq"),
        ForeignKeyConstraint(
            ["server_id", "owner_discord_id"],
            ["owners.server_id", "owners.discord_id"],
            ondelete="CASCADE",
            name="kennels_owner_fk",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))
    owner_discord_id: Mapped[int] = mapped_column(BigInteger)

    pooch_limit: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owner: Mapped[Owner] = relationship("Owner", foreign_keys=[server_id, owner_discord_id], back_populates="kennels")

    kennel_pooch_rows: Mapped[list[KennelPooch]] = relationship(
        "KennelPooch",
        back_populates="kennel",
        cascade="all, delete-orphan",
    )

    pooches = association_proxy("kennel_pooch_rows", "pooch")
