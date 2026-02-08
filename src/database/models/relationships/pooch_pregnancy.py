from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from ..base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch


class PoochPregnancy(Base):
    __tablename__ = "pooch_pregnancy"
    __table_args__ = (
        UniqueConstraint("server_id", "fetus_id", name="pooch_pregnancy_unique_fetus_per_server"),
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="CASCADE",
            name="pooch_pregnancy_mother_fk",
        ),
        ForeignKeyConstraint(
            ["server_id", "fetus_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="CASCADE",
            name="pooch_pregnancy_fetus_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fetus_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    mother: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[server_id, pooch_id],
        back_populates="pregnancies_as_mother",
    )

    fetus: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[server_id, fetus_id],
        back_populates="pregnancy_as_fetus_rows",
    )
