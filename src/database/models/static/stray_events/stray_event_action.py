from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_ACTION_TYPE

if TYPE_CHECKING:
    from .stray_event import StrayEvent
    from .stray_event_outcome import StrayEventOutcome


class StrayEventAction(Base):
    __tablename__ = "stray_event_actions"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(stray_event_id, stray_event_outcome_id) = 1",
            name="stray_event_actions_exactly_one_parent",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stray_event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stray_events.id", ondelete="CASCADE"), nullable=True
    )
    stray_event_outcome_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stray_event_outcomes.id", ondelete="CASCADE"), nullable=True
    )

    action_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(EVENT_ACTION_TYPE, nullable=False)
    repeat: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    stray_event: Mapped[StrayEvent | None] = relationship(
        "StrayEvent", back_populates="actions", foreign_keys=[stray_event_id]
    )
    outcome: Mapped[StrayEventOutcome | None] = relationship(
        "StrayEventOutcome", back_populates="actions", foreign_keys=[stray_event_outcome_id]
    )
