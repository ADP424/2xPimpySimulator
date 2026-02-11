from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch


class PoochPregnancy(Base):
    __tablename__ = "pooch_pregnancy"
    __table_args__ = (UniqueConstraint("fetus_id", name="pooch_pregnancy_unique_fetus"),)

    mother_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    fetus_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)

    mother: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[mother_id],
        back_populates="pregnancies_as_mother",
    )

    fetus: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[fetus_id],
        back_populates="pregnancy_as_fetus_rows",
    )
