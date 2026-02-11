from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch


class HellPooch(Base):
    __tablename__ = "hell_pooches"

    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)

    damned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    pooch: Mapped[Pooch] = relationship("Pooch", foreign_keys=[pooch_id], back_populates="hell_row")
