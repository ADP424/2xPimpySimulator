from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import EventOptionAdvancedOptions

if TYPE_CHECKING:
    from .event import Event
    from .event_action import EventAction
    from .event_outcome import EventOutcome


class EventOption(Base):
    __tablename__ = "event_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)

    option_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    min_money: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_bloodskulls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    advanced_options: Mapped[EventOptionAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    event: Mapped[Event] = relationship("Event", back_populates="options")
    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="option",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.option_id",
        order_by="EventAction.action_order",
    )
    outcomes: Mapped[list[EventOutcome]] = relationship(
        "EventOutcome",
        back_populates="option",
        cascade="all, delete-orphan",
        order_by="EventOutcome.outcome_order",
    )
