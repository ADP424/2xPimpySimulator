from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from ..base import Base

if TYPE_CHECKING:
    from ..owner import Owner
    from ..pooch import Pooch


class GraveyardPooch(Base):
    __tablename__ = "graveyard_pooches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "owner_discord_id"],
            ["owners.server_id", "owners.discord_id"],
            ondelete="CASCADE",
            name="graveyard_owner_fk",
        ),
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="RESTRICT",
            name="graveyard_pooch_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    owner_discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    buried_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owner: Mapped[Owner] = relationship(
        "Owner", foreign_keys=[server_id, owner_discord_id], back_populates="graveyard_rows"
    )
    pooch: Mapped[Pooch] = relationship("Pooch", foreign_keys=[server_id, pooch_id])
