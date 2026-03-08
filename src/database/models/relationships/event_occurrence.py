from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from database.models.event_types import EventContextDict, EventResultDict

if TYPE_CHECKING:
    from ..owner import Owner
    from ..static import Event, EventOption


class EventOccurrence(Base):
    __tablename__ = "event_occurrences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    owner_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"), nullable=False
    )

    context: Mapped[EventContextDict] = mapped_column(JSONB, nullable=False, default=dict)
    result_summary: Mapped[EventResultDict] = mapped_column(JSONB, nullable=False, default=dict)

    triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    responded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    selected_option_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("event_options.id", ondelete="SET NULL"), nullable=True
    )
    timed_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    event: Mapped[Event] = relationship("Event")
    owner: Mapped[Owner] = relationship("Owner")
    selected_option: Mapped[EventOption] = relationship("EventOption")
