from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import EventOptionAdvancedOptions, OwnerEventFilterSpec

if TYPE_CHECKING:
    from .event import Event
    from .event_action import EventAction
    from .event_outcome import EventOutcome


class EventOption(Base):
    __tablename__ = "owner_event_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("owner_events.id", ondelete="CASCADE"), nullable=False)

    option_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    filter: Mapped[OwnerEventFilterSpec] = mapped_column(JSONB, nullable=False, default=dict)
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

    @property
    def min_money(self) -> int:
        return int(self.filter.get("min_money", 0))

    @property
    def min_bloodskulls(self) -> int:
        return int(self.filter.get("min_bloodskulls", 0))
