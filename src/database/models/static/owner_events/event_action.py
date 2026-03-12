from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_ACTION_TYPE, EVENT_TARGET_TYPE
from ...event_types import EventActionParameters

if TYPE_CHECKING:
    from ..server_events import ServerEvent, ServerEventOption, ServerEventOutcome
    from .event import Event
    from .event_option import EventOption
    from .event_outcome import EventOutcome


class EventAction(Base):
    __tablename__ = "event_actions"
    __table_args__ = (
        CheckConstraint(
            (
                "num_nonnulls(event_id, option_id, outcome_id, server_event_id, "
                "server_event_option_id, server_event_outcome_id) = 1"
            ),
            name="event_actions_exactly_one_parent",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("owner_events.id", ondelete="CASCADE"), nullable=True
    )
    option_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("owner_event_options.id", ondelete="CASCADE"), nullable=True
    )
    outcome_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("owner_event_outcomes.id", ondelete="CASCADE"), nullable=True
    )
    server_event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("server_events.id", ondelete="CASCADE"), nullable=True
    )
    server_event_option_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("server_event_options.id", ondelete="CASCADE"), nullable=True
    )
    server_event_outcome_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("server_event_outcomes.id", ondelete="CASCADE"), nullable=True
    )

    action_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(EVENT_ACTION_TYPE, nullable=False)
    target_type: Mapped[str] = mapped_column(EVENT_TARGET_TYPE, nullable=False, server_default=text("'owner'"))

    parameters: Mapped[EventActionParameters] = mapped_column(JSONB, nullable=False, default=dict)

    event: Mapped[Event | None] = relationship("Event", back_populates="actions", foreign_keys=[event_id])
    option: Mapped[EventOption | None] = relationship("EventOption", back_populates="actions", foreign_keys=[option_id])
    outcome: Mapped[EventOutcome | None] = relationship(
        "EventOutcome", back_populates="actions", foreign_keys=[outcome_id]
    )
    server_event: Mapped[ServerEvent | None] = relationship(
        "ServerEvent", back_populates="actions", foreign_keys=[server_event_id]
    )
    server_event_option: Mapped[ServerEventOption | None] = relationship(
        "ServerEventOption", back_populates="actions", foreign_keys=[server_event_option_id]
    )
    server_event_outcome: Mapped[ServerEventOutcome | None] = relationship(
        "ServerEventOutcome", back_populates="actions", foreign_keys=[server_event_outcome_id]
    )
