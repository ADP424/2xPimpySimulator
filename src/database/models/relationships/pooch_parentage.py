from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch


class PoochParentage(Base):
    __tablename__ = "pooch_parentage"

    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    father_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pooches.id", ondelete="SET NULL"), nullable=True
    )
    mother_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pooches.id", ondelete="SET NULL"), nullable=True
    )

    child: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[child_id],
        back_populates="parentage",
        uselist=False,
    )

    father: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[father_id],
        uselist=False,
        viewonly=True,
    )

    mother: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[mother_id],
        uselist=False,
        viewonly=True,
    )
