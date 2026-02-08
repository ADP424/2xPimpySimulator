from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base

if TYPE_CHECKING:
    from .pooch import Pooch
    from .kennel import Kennel
    from .relationships.graveyard_pooch import GraveyardPooch


class Owner(Base):
    __tablename__ = "owners"

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    dollars: Mapped[int] = mapped_column(Integer, default=100)
    bloodskulls: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owned_pooches: Mapped[list[Pooch]] = relationship(
        "Pooch", back_populates="owner", foreign_keys="Pooch.server_id, Pooch.owner_discord_id"
    )

    kennels: Mapped[list[Kennel]] = relationship(
        "Kennel",
        back_populates="owner",
        cascade="all, delete-orphan",
        overlaps="server",
    )

    graveyard_rows: Mapped[list[GraveyardPooch]] = relationship(
        "GraveyardPooch",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    graveyard = association_proxy("graveyard_rows", "pooch")

    server = relationship("Server", back_populates="owners", foreign_keys=[server_id])
