from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    from ..entities import Pooch

# Snapshot kind constants
SNAPSHOT_BIRTH = "birth"
SNAPSHOT_DEATH = "death"
SNAPSHOT_OWNERSHIP = "ownership"
SNAPSHOT_VET_INJURIES = "vet_injuries"
SNAPSHOT_VET_MUTATIONS = "vet_mutations"
SNAPSHOT_MEDICAL_EXAM = "medical_exam"
SNAPSHOT_VET_DISEASES = "vet_diseases"


class PoochSnapshot(Base):
    __tablename__ = "pooch_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pooch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Optional list of integer IDs (injury IDs or mutation IDs) recorded at the time of a vet snapshot
    entity_ids: Mapped[Optional[list[int]]] = mapped_column(ARRAY(Integer), nullable=True)

    pooch: Mapped["Pooch"] = relationship("Pooch", back_populates="pooch_snapshots")
