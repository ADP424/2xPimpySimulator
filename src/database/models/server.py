from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base

if TYPE_CHECKING:
    from .vendor import Vendor
    from .relationships.owner_server import OwnerServer


class Server(Base):
    __tablename__ = "servers"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_channel_discord_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    vendors: Mapped[list[Vendor]] = relationship("Vendor", back_populates="server", cascade="all, delete-orphan")

    owner_server_rows: Mapped[list[OwnerServer]] = relationship(
        "OwnerServer",
        back_populates="server",
        cascade="all, delete-orphan",
    )
    owners = association_proxy("owner_server_rows", "owner")
