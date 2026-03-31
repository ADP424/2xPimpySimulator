from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base

if TYPE_CHECKING:
    from ...static import Injury
    from ..entities import Pooch


class PoochInjury(Base):
    __tablename__ = "pooch_injuries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), nullable=False)
    injury_id: Mapped[int] = mapped_column(Integer, ForeignKey("injuries.id", ondelete="RESTRICT"), nullable=False)
    persistence: Mapped[int] = mapped_column(Integer, nullable=True)

    injury: Mapped[Injury] = relationship("Injury")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_injuries")
