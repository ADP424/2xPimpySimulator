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


class StrayEvent(Base):
    __tablename__ = "stray_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    flavor_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    severity: Mapped[str] = mapped_column(EVENT_SEVERITY, nullable=False, server_default=text("'minor'"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))

    triggered_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filter: Mapped[StrayEventFilterSpec] = mapped_column(JSONB, nullable=False, default=dict)
    advanced_options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    actions: Mapped[list[StrayEventAction]] = relationship(
        "StrayEventAction",
        back_populates="stray_event",
        cascade="all, delete-orphan",
        order_by="StrayEventAction.action_order",
    )
