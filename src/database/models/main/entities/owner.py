from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text, text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ..relationships.graveyard_pooch import GraveyardPooch
    from ..relationships.owner_server import OwnerServer
    from .kennel import Kennel
    from .pooch import Pooch


class Owner(Base):
    __tablename__ = "owners"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    dollars: Mapped[int] = mapped_column(Integer, default=100)
    bloodskulls: Mapped[int] = mapped_column(Integer, default=0)
    bones: Mapped[int] = mapped_column(Integer, default=0)
    begged_today: Mapped[bool] = mapped_column(Boolean, default=True)
    visited_park_today: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owned_pooches: Mapped[list[Pooch]] = relationship(
        "Pooch", back_populates="owner", foreign_keys="Pooch.owner_discord_id"
    )

    kennels: Mapped[list[Kennel]] = relationship("Kennel", back_populates="owner", cascade="all, delete-orphan")

    owner_server_rows: Mapped[list[OwnerServer]] = relationship(
        "OwnerServer",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    servers = association_proxy("owner_server_rows", "server")

    graveyard_rows: Mapped[list[GraveyardPooch]] = relationship(
        "GraveyardPooch",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    graveyard = association_proxy("graveyard_rows", "pooch")
