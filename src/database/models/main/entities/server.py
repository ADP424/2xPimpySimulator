from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ..relationships.owner_server import OwnerServer
    from ..relationships.stray_pooch import StrayPooch
    from .vendor import Vendor


class Server(Base):
    __tablename__ = "servers"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_channel_discord_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    vendors: Mapped[list[Vendor]] = relationship("Vendor", back_populates="server", cascade="all, delete-orphan")

    stray_rows: Mapped[list[StrayPooch]] = relationship(
        "StrayPooch", back_populates="server", cascade="all, delete-orphan"
    )

    owner_server_rows: Mapped[list[OwnerServer]] = relationship(
        "OwnerServer",
        back_populates="server",
        cascade="all, delete-orphan",
    )
    owners = association_proxy("owner_server_rows", "owner")
