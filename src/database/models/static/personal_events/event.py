from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_SEVERITY, RARITY
from ...event_types import EventAdvancedOptions

if TYPE_CHECKING:
    from .event_action import EventAction
    from .event_option import EventOption


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    flavor_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    severity: Mapped[str] = mapped_column(EVENT_SEVERITY, nullable=False, server_default=text("'moderate'"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))
    requires_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)

    min_pooches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_kennels: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_money: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_bloodskulls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    advanced_options: Mapped[EventAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

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
