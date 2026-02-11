from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base

if TYPE_CHECKING:
    from .owner import Owner
    from .relationships.kennel_pooch import KennelPooch


class Kennel(Base):
    __tablename__ = "kennels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    owner_discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(Text)
    pooch_limit: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owner: Mapped[Owner] = relationship("Owner", foreign_keys=[owner_discord_id], back_populates="kennels")

    kennel_pooch_rows: Mapped[list[KennelPooch]] = relationship(
        "KennelPooch",
        back_populates="kennel",
        cascade="all, delete-orphan",
    )
    pooches = association_proxy("kennel_pooch_rows", "pooch")
