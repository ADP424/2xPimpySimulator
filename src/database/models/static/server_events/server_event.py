from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums import EVENT_SEVERITY, RARITY
from ...event_types import ServerEventAdvancedOptions

if TYPE_CHECKING:
    from ..owner_events import EventAction
    from .server_event_menu import ServerEventMenu
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

    # Replaces min_owners / resolution_strategy — full eligibility filter as JSONB
    filter: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Serialised list of action specs fired server-side when no qualifying participants exist at resolution
    default_actions_data: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    parameters: Mapped[ServerEventAdvancedOptions] = mapped_column(JSONB, nullable=False, default=dict)

    # Actions fired immediately at event trigger (target_type="server")
    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="server_event",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.server_event_id",
        order_by="EventAction.action_order",
    )
    menus: Mapped[list[ServerEventMenu]] = relationship(
        "ServerEventMenu",
        back_populates="server_event",
        cascade="all, delete-orphan",
        order_by="ServerEventMenu.menu_order",
    )
    outcomes: Mapped[list[ServerEventOutcome]] = relationship(
        "ServerEventOutcome",
        back_populates="server_event",
        cascade="all, delete-orphan",
        order_by="ServerEventOutcome.outcome_order",
    )
