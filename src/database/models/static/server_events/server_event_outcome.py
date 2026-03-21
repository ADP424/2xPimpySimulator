from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import ServerEventOutcomeAdvancedOptions

if TYPE_CHECKING:
    from ..owner_events import EventAction
    from .server_event import ServerEvent


class ServerEventOutcome(Base):
    __tablename__ = "server_event_outcomes"
    __table_args__ = (
        CheckConstraint("chance IS NULL OR (chance >= 0 AND chance <= 1)", name="server_event_outcomes_chance_range"),
        CheckConstraint(
            "(min_rank IS NULL OR min_rank >= 1) AND "
            "(max_rank IS NULL OR max_rank >= 1) AND "
            "(min_rank IS NULL OR max_rank IS NULL OR min_rank <= max_rank)",
            name="server_event_outcomes_rank_bounds",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("server_events.id", ondelete="CASCADE"), nullable=False
    )

    outcome_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # "ranked_players" | "all_participants" | "server" | "non_participants"
    target: Mapped[str] = mapped_column(Text, nullable=False, default="ranked_players")
    min_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chance: Mapped[float | None] = mapped_column(Float, nullable=True)

    advanced_options: Mapped[ServerEventOutcomeAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    server_event: Mapped[ServerEvent] = relationship("ServerEvent", back_populates="outcomes")
    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="server_event_outcome",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.server_event_outcome_id",
        order_by="EventAction.action_order",
    )
