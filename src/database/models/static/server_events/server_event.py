from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_SEVERITY, RARITY
from ...event_types import ServerEventAdvancedOptions

if TYPE_CHECKING:
    from ..owner_events import EventAction
    from .server_event_option import ServerEventOption
    from .server_event_outcome import ServerEventOutcome


class ServerEvent(Base):
    __tablename__ = "server_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    flavor_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    severity: Mapped[str] = mapped_column(EVENT_SEVERITY, nullable=False, server_default=text("'moderate'"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))

    min_owners: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolution_strategy: Mapped[str] = mapped_column(Text, nullable=False, default="random_winner")

    advanced_options: Mapped[ServerEventAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="server_event",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.server_event_id",
        order_by="EventAction.action_order",
    )
    options: Mapped[list[ServerEventOption]] = relationship(
        "ServerEventOption",
        back_populates="server_event",
        cascade="all, delete-orphan",
        order_by="ServerEventOption.option_order",
    )
    outcomes: Mapped[list[ServerEventOutcome]] = relationship(
        "ServerEventOutcome",
        back_populates="server_event",
        cascade="all, delete-orphan",
        order_by="ServerEventOutcome.outcome_order",
    )
