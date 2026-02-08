from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base

if TYPE_CHECKING:
    from .pooch import Pooch
    from .owner import Owner
    from .vendor import Vendor
    from .kennel import Kennel
    from .relationships.hell_pooch import HellPooch


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    pooches: Mapped[list[Pooch]] = relationship(
        "Pooch", back_populates="server", cascade="all, delete-orphan", overlaps="owned_pooches,owner,vendor"
    )

    owners: Mapped[list[Owner]] = relationship("Owner", back_populates="server", cascade="all, delete-orphan")
    vendors: Mapped[list[Vendor]] = relationship("Vendor", back_populates="server", cascade="all, delete-orphan")
    kennels: Mapped[list[Kennel]] = relationship(
        "Kennel", back_populates="server", cascade="all, delete-orphan", overlaps="kennels,owner"
    )

    hell_rows: Mapped[list[HellPooch]] = relationship(
        "HellPooch", back_populates="server", cascade="all, delete-orphan", overlaps="hell_rows"
    )
    hell = association_proxy("hell_rows", "pooch")
