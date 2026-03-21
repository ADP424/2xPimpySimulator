from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_SEVERITY, RARITY
from ...event_types import EventAdvancedOptions, OwnerEventFilterSpec

if TYPE_CHECKING:
    from .event_action import EventAction
    from .event_option import EventOption


class Event(Base):
    __tablename__ = "owner_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    flavor_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    severity: Mapped[str] = mapped_column(EVENT_SEVERITY, nullable=False, server_default=text("'moderate'"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))
    requires_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)

    triggered_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filter: Mapped[OwnerEventFilterSpec] = mapped_column(JSONB, nullable=False, default=dict)
    parameters: Mapped[EventAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="event",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.event_id",
        order_by="EventAction.action_order",
    )
    options: Mapped[list[EventOption]] = relationship(
        "EventOption", back_populates="event", cascade="all, delete-orphan", order_by="EventOption.option_order"
    )

    @property
    def min_pooches(self) -> int:
        return self.filter.get("min_pooches", 0)

    @property
    def min_kennels(self) -> int:
        return self.filter.get("min_kennels", 0)

    @property
    def min_money(self) -> int:
        return self.filter.get("min_money", 0)

    @property
    def min_bloodskulls(self) -> int:
        return self.filter.get("min_bloodskulls", 0)
