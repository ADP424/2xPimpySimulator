from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:
    from ..kennel import Kennel
    from ..pooch import Pooch


class KennelPooch(Base):
    __tablename__ = "kennel_pooches"

    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    kennel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kennels.id", ondelete="CASCADE"), nullable=False)

    pooch: Mapped[Pooch] = relationship("Pooch", foreign_keys=[pooch_id], back_populates="kennel_row")
    kennel: Mapped[Kennel] = relationship("Kennel", foreign_keys=[kennel_id], back_populates="kennel_pooch_rows")
