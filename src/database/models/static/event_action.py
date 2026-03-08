from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from database.models.enums import EVENT_ACTION_TYPE, EVENT_TARGET_TYPE
from database.models.event_types import EventActionParameters

if TYPE_CHECKING:
    from .event import Event
    from .event_option import EventOption
    from .event_outcome import EventOutcome


class EventAction(Base):
    __tablename__ = "event_actions"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(event_id, option_id, outcome_id) = 1",
            name="event_actions_exactly_one_parent",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
    )
    option_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("event_options.id", ondelete="CASCADE"),
        nullable=True,
    )
    outcome_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("event_outcomes.id", ondelete="CASCADE"),
        nullable=True,
    )

    action_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(EVENT_ACTION_TYPE, nullable=False)
    target_type: Mapped[str] = mapped_column(EVENT_TARGET_TYPE, nullable=False, server_default=text("'owner'"))

    parameters: Mapped[EventActionParameters] = mapped_column(JSONB, nullable=False, default=dict)

    event: Mapped[Event] = relationship("Event", back_populates="actions", foreign_keys=[event_id])
    option: Mapped[EventOption] = relationship("EventOption", back_populates="actions", foreign_keys=[option_id])
    outcome: Mapped[EventOutcome] = relationship("EventOutcome", back_populates="actions", foreign_keys=[outcome_id])
