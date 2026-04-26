from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    from ...static import Disease
    from ..entities import Pooch


class PoochDiseaseImmunity(Base):
    __tablename__ = "pooch_disease_immunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), nullable=False)
    disease_id: Mapped[int] = mapped_column(Integer, ForeignKey("diseases.id", ondelete="RESTRICT"), nullable=False)
    immune_until_day: Mapped[int] = mapped_column(Integer, nullable=False)

    disease: Mapped[Disease] = relationship("Disease")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_disease_immunities")
