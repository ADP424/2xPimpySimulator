from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from database.models.base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch
    from ..static.breed import Breed


class PoochBreed(Base):
    __tablename__ = "pooch_breeds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="CASCADE",
            name="pooch_breeds_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    breed_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("breeds.id", ondelete="RESTRICT"), primary_key=True)

    weight: Mapped[int] = mapped_column(Integer, nullable=False)

    breed: Mapped[Breed] = relationship("Breed")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_breeds")
