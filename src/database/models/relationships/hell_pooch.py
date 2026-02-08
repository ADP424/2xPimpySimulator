from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from ..base import Base

if TYPE_CHECKING:
    from ..server import Server
    from ..pooch import Pooch


class HellPooch(Base):
    __tablename__ = "hell_pooches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="RESTRICT",
            name="hell_pooch_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    damned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    server: Mapped[Server] = relationship("Server", foreign_keys=[server_id], back_populates="hell_rows")
    pooch: Mapped[Pooch] = relationship("Pooch", foreign_keys=[server_id, pooch_id])
