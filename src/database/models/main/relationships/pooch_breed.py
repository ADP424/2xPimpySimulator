from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ...static import Breed
    from ..entities import Pooch


class PoochBreed(Base):
    __tablename__ = "pooch_breeds"
    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    breed_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("breeds.id", ondelete="RESTRICT"), primary_key=True)

    weight: Mapped[int] = mapped_column(Integer, nullable=False)

    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_breeds")
    breed: Mapped[Breed] = relationship("Breed")
