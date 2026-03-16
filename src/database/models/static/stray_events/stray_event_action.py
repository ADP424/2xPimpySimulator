from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_ACTION_TYPE, EVENT_TARGET_TYPE

if TYPE_CHECKING:
    from .stray_event import StrayEvent


class StrayEventAction(Base):
    __tablename__ = "stray_event_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stray_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stray_events.id", ondelete="CASCADE"), nullable=False
    )

    action_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(EVENT_ACTION_TYPE, nullable=False)
    target_type: Mapped[str] = mapped_column(EVENT_TARGET_TYPE, nullable=False, server_default=text("'pooch'"))
    repeat: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    stray_event: Mapped[StrayEvent] = relationship("StrayEvent", back_populates="actions")
