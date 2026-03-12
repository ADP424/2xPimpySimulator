from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import EventOutcomeAdvancedOptions

if TYPE_CHECKING:
    from .event_action import EventAction
    from .event_option import EventOption


class EventOutcome(Base):
    __tablename__ = "owner_event_outcomes"
    __table_args__ = (
        CheckConstraint("chance IS NULL OR (chance >= 0 AND chance <= 1)", name="owner_event_outcomes_chance_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    option_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owner_event_options.id", ondelete="CASCADE"), nullable=False
    )

    outcome_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chance: Mapped[float | None] = mapped_column(Float, nullable=True)

    advanced_options: Mapped[EventOutcomeAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    option: Mapped[EventOption] = relationship("EventOption", back_populates="outcomes")
    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="outcome",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.outcome_id",
        order_by="EventAction.action_order",
    )
