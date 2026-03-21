from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from .server_event import ServerEvent
    from .server_event_menu_option import ServerEventMenuOption


class ServerEventMenu(Base):
    __tablename__ = "server_event_menus"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("server_events.id", ondelete="CASCADE"), nullable=False
    )

    menu_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(Text, nullable=False)  # slug used in depends_on and UI
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # -1 means unlimited
    max_uses_per_player: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # JSON list of menu name slugs that must be used before this menu becomes available
    depends_on: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    server_event: Mapped[ServerEvent] = relationship("ServerEvent", back_populates="menus")
    options: Mapped[list[ServerEventMenuOption]] = relationship(
        "ServerEventMenuOption",
        back_populates="menu",
        cascade="all, delete-orphan",
        order_by="ServerEventMenuOption.option_order",
    )
