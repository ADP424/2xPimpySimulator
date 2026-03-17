from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_SEVERITY, RARITY
from ...event_types import StrayEventFilterSpec

if TYPE_CHECKING:
    from .stray_event_action import StrayEventAction
    from .stray_event_outcome import StrayEventOutcome


class StrayEvent(Base):
    __tablename__ = "stray_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)

    severity: Mapped[str] = mapped_column(EVENT_SEVERITY, nullable=False, server_default=text("'minor'"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))

    triggered_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filter: Mapped[StrayEventFilterSpec] = mapped_column(JSONB, nullable=False, default=dict)

    actions: Mapped[list[StrayEventAction]] = relationship(
        "StrayEventAction",
        back_populates="stray_event",
        cascade="all, delete-orphan",
        foreign_keys="StrayEventAction.stray_event_id",
        order_by="StrayEventAction.action_order",
    )
    outcomes: Mapped[list[StrayEventOutcome]] = relationship(
        "StrayEventOutcome",
        back_populates="stray_event",
        cascade="all, delete-orphan",
        order_by="StrayEventOutcome.outcome_order",
    )
