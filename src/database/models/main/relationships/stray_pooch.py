from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ..entities import Pooch, Server


class StrayPooch(Base):
    __tablename__ = "stray_pooches"

    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    server_discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.discord_id", ondelete="CASCADE"))

    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    pooch: Mapped["Pooch"] = relationship("Pooch", foreign_keys=[pooch_id], back_populates="stray_row")
    server: Mapped["Server"] = relationship("Server", foreign_keys=[server_discord_id], back_populates="stray_rows")
