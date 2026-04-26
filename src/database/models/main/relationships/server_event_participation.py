from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import EventContextDict, EventResultDict

if TYPE_CHECKING:
    from ..entities import Owner
    from .server_event_occurrence import ServerEventOccurrence


class ServerEventParticipation(Base):
    __tablename__ = "server_event_participations"
    __table_args__ = (UniqueConstraint("occurrence_id", "owner_discord_id", name="server_event_one_entry_per_owner"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurrence_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("server_event_occurrences.id", ondelete="CASCADE"), nullable=False
    )
    owner_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"), nullable=False
    )

    # Snapshot of the owner's event context at first participation
    context: Mapped[EventContextDict] = mapped_column(JSONB, nullable=False, default=dict)

    # All individual option submissions across all menus, stored as a JSONB array.
    # Each element: {
    #   "menu_name": str, "menu_option_id": int, "option_label": str,
    #   "selected_pooch_id": int|null, "context_snapshot": {...},
    #   "score_contribution": float, "immediate_result": {...}, "submitted_at": str (ISO)
    # }
    submissions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Immediate result from the first option actions (kept for backwards display compat)
    immediate_result: Mapped[EventResultDict] = mapped_column(JSONB, nullable=False, default=dict)
    resolution_result: Mapped[EventResultDict] = mapped_column(JSONB, nullable=False, default=dict)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    occurrence: Mapped[ServerEventOccurrence] = relationship("ServerEventOccurrence", back_populates="participations")
    owner: Mapped[Owner] = relationship("Owner")
