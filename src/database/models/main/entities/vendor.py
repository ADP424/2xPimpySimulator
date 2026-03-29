from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ..relationships.vendor_desired_breed import VendorDesiredBreed
    from ..relationships.vendor_desired_mutation import VendorDesiredMutation
    from ..relationships.vendor_pooch_for_sale import VendorPoochForSale
    from .pooch import Pooch


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("server_discord_id", "name", name="vendors_server_discord_id_name_uniq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.discord_id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(Text)
    price_markup: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("1.0")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owned_pooches: Mapped[list[Pooch]] = relationship(
        "Pooch",
        back_populates="vendor",
        foreign_keys="Pooch.vendor_id",
    )

    pooches_for_sale_rows: Mapped[list[VendorPoochForSale]] = relationship(
        "VendorPoochForSale",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    pooches_for_sale = association_proxy("pooches_for_sale_rows", "pooch")

    desired_mutation_rows: Mapped[list[VendorDesiredMutation]] = relationship(
        "VendorDesiredMutation",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    desired_breed_rows: Mapped[list[VendorDesiredBreed]] = relationship(
        "VendorDesiredBreed",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )

    server = relationship("Server", back_populates="vendors", foreign_keys=[server_discord_id])
