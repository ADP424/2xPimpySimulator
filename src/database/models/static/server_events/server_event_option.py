from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...event_types import ServerEventOptionAdvancedOptions

if TYPE_CHECKING:
    from ..owner_events import EventAction
    from .server_event import ServerEvent


class ServerEventOption(Base):
    __tablename__ = "server_event_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("server_events.id", ondelete="CASCADE"), nullable=False
    )

    option_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    min_money: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_bloodskulls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_pooch_selection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parameters: Mapped[ServerEventOptionAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    server_event: Mapped[ServerEvent] = relationship("ServerEvent", back_populates="options")
    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="server_event_option",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.server_event_option_id",
        order_by="EventAction.action_order",
    )
