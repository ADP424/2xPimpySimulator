from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    from ...static import Disease
    from ..entities import Pooch


class PoochDisease(Base):
    __tablename__ = "pooch_diseases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), nullable=False)
    disease_id: Mapped[int] = mapped_column(Integer, ForeignKey("diseases.id", ondelete="RESTRICT"), nullable=False)
    contracted_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    treated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    displayed_symptom: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    disease: Mapped[Disease] = relationship("Disease")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_diseases")
