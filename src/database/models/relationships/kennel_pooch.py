from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from database.models.base import Base

if TYPE_CHECKING:
    from ..kennel import Kennel
    from ..pooch import Pooch


class KennelPooch(Base):
    __tablename__ = "kennel_pooches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "kennel_id"],
            ["kennels.server_id", "kennels.id"],
            ondelete="CASCADE",
            name="kennel_pooches_kennel_fk",
        ),
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="RESTRICT",
            name="kennel_pooches_pooch_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    kennel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    kennel: Mapped[Kennel] = relationship(
        "Kennel", foreign_keys=[server_id, kennel_id], back_populates="kennel_pooch_rows"
    )
    pooch: Mapped[Pooch] = relationship("Pooch", foreign_keys=[server_id, pooch_id], back_populates="kennel_rows")
