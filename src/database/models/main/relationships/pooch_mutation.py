from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    from ...static import Mutation
    from ..entities import Pooch


class PoochMutation(Base):
    __tablename__ = "pooch_mutations"
    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    mutation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mutations.id", ondelete="RESTRICT"), primary_key=True
    )
    displayed_symptom: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    mutation: Mapped[Mutation] = relationship("Mutation")
    pooch: Mapped[Pooch] = relationship("Pooch", back_populates="pooch_mutations")
