from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from .stray_event import StrayEvent
    from .stray_event_action import StrayEventAction


class StrayEventOutcome(Base):
    __tablename__ = "stray_event_outcomes"
    __table_args__ = (
        CheckConstraint(
            "chance IS NULL OR (chance >= 0 AND chance <= 1)",
            name="stray_event_outcomes_chance_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stray_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stray_events.id", ondelete="CASCADE"), nullable=False
    )

    outcome_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chance: Mapped[float | None] = mapped_column(Float, nullable=True)

    stray_event: Mapped[StrayEvent] = relationship("StrayEvent", back_populates="outcomes")
    actions: Mapped[list[StrayEventAction]] = relationship(
        "StrayEventAction",
        back_populates="outcome",
        cascade="all, delete-orphan",
        foreign_keys="StrayEventAction.stray_event_outcome_id",
        order_by="StrayEventAction.action_order",
    )
