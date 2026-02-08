from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from database.models.base import Base

if TYPE_CHECKING:
    from ..pooch import Pooch
    from ..static.mutation import Mutation


class PoochMutation(Base):
    __tablename__ = "pooch_mutations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="CASCADE",
            name="pooch_mutations_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mutation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mutations.id", ondelete="RESTRICT"), primary_key=True
    )

    mutation: Mapped[Mutation] = relationship("Mutation")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_mutations")
