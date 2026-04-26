from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ..owner_events import EventAction
    from .server_event_menu import ServerEventMenu


class ServerEventMenuOption(Base):
    __tablename__ = "server_event_menu_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    menu_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("server_event_menus.id", ondelete="CASCADE"), nullable=False
    )

    option_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # OwnerEventFilterSpec as JSONB — controls who can see/use this option
    filter: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Requirements for submission (e.g. {"pooch": {"filter": {...}}})
    requires: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # ScoringSpec as JSONB
    scoring: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    menu: Mapped[ServerEventMenu] = relationship("ServerEventMenu", back_populates="options")
    actions: Mapped[list[EventAction]] = relationship(
        "EventAction",
        back_populates="server_event_menu_option",
        cascade="all, delete-orphan",
        foreign_keys="EventAction.server_event_menu_option_id",
        order_by="EventAction.action_order",
    )
