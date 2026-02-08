from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from ..base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch


class PoochParentage(Base):
    __tablename__ = "pooch_parentage"

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    father_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mother_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="CASCADE",
            name="pooch_parentage_child_fk",
        ),
        ForeignKeyConstraint(
            ["server_id", "father_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="SET NULL",
            name="pooch_parentage_father_fk",
        ),
        ForeignKeyConstraint(
            ["server_id", "mother_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="SET NULL",
            name="pooch_parentage_mother_fk",
        ),
    )

    child: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[server_id, pooch_id],
        back_populates="parentage",
        uselist=False,
    )

    father: Mapped[Pooch | None] = relationship(
        "Pooch",
        foreign_keys=[server_id, father_id],
        uselist=False,
        viewonly=True,
    )

    mother: Mapped[Pooch | None] = relationship(
        "Pooch",
        foreign_keys=[server_id, mother_id],
        uselist=False,
        viewonly=True,
    )
