from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import EventResultDict, ServerEventContextDict

if TYPE_CHECKING:
    from ...static import ServerEvent
    from ..entities import Server
    from .server_event_participation import ServerEventParticipation


class ServerEventOccurrence(Base):
    __tablename__ = "server_event_occurrences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.discord_id", ondelete="CASCADE"), nullable=False
    )
    server_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("server_events.id", ondelete="CASCADE"), nullable=False
    )

    context: Mapped[ServerEventContextDict] = mapped_column(JSONB, nullable=False, default=dict)
    result_summary: Mapped[EventResultDict] = mapped_column(JSONB, nullable=False, default=dict)

    triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    message_discord_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    server: Mapped[Server] = relationship("Server")
    server_event: Mapped[ServerEvent] = relationship("ServerEvent")
    participations: Mapped[list[ServerEventParticipation]] = relationship(
        "ServerEventParticipation",
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="ServerEventParticipation.participated_at",
    )
