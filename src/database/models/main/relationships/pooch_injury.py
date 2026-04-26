from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    from ...static import Injury
    from ..entities import Pooch


class PoochInjury(Base):
    __tablename__ = "pooch_injuries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), nullable=False)
    injury_id: Mapped[int] = mapped_column(Integer, ForeignKey("injuries.id", ondelete="RESTRICT"), nullable=False)
    persistence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    treated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_treated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    displayed_symptom: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    injury: Mapped[Injury] = relationship("Injury")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_injuries")
