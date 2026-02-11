from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from ..owner import Owner
    from ..pooch import Pooch


class GraveyardPooch(Base):
    __tablename__ = "graveyard_pooches"

    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    owner_discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"))

    buried_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owner: Mapped[Owner] = relationship("Owner", foreign_keys=[owner_discord_id], back_populates="graveyard_rows")
    pooch: Mapped[Pooch] = relationship("Pooch", foreign_keys=[pooch_id], back_populates="graveyard_row")
