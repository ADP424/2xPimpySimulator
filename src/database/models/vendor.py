from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, Text, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base

if TYPE_CHECKING:
    from .pooch import Pooch
    from .relationships.vendor_pooch_for_sale import VendorPoochForSale


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint("server_id", "id", name="vendors_server_id_id_uniq"),
        UniqueConstraint("server_id", "name", name="vendors_server_id_name_uniq"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(Text)

    desired_mutation_1: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("mutations.id"), nullable=True)
    desired_mutation_2: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("mutations.id"), nullable=True)
    desired_mutation_3: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("mutations.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owned_pooches: Mapped[list[Pooch]] = relationship(
        "Pooch",
        back_populates="vendor",
        foreign_keys="Pooch.server_id, Pooch.vendor_id",
        overlaps="owned_pooches,owner,pooches,server",
    )

    pooches_for_sale_rows: Mapped[list[VendorPoochForSale]] = relationship(
        "VendorPoochForSale",
        back_populates="vendor",
        cascade="all, delete-orphan",
        overlaps="vendor_pooch_for_sale_rows",
    )
    pooches_for_sale = association_proxy("pooches_for_sale_rows", "pooch")

    server = relationship("Server", back_populates="vendors", foreign_keys=[server_id])
