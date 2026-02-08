from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint

from ..base import Base

if TYPE_CHECKING:
    from ..vendor import Vendor
    from ..pooch import Pooch


class VendorPoochForSale(Base):
    __tablename__ = "vendor_pooches_for_sale"
    __table_args__ = (
        UniqueConstraint("server_id", "pooch_id", name="vendor_sale_unique_pooch_per_server"),
        ForeignKeyConstraint(
            ["server_id", "vendor_id"],
            ["vendors.server_id", "vendors.id"],
            ondelete="CASCADE",
            name="vendor_sale_vendor_fk",
        ),
        ForeignKeyConstraint(
            ["server_id", "pooch_id"],
            ["pooches.server_id", "pooches.id"],
            ondelete="RESTRICT",
            name="vendor_sale_pooch_fk",
        ),
    )

    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    vendor_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pooch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    vendor: Mapped[Vendor] = relationship(
        "Vendor",
        foreign_keys=[server_id, vendor_id],
        back_populates="pooches_for_sale_rows",
        overlaps="vendor_pooch_for_sale_rows",
    )
    pooch: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[server_id, pooch_id],
        back_populates="vendor_pooch_for_sale_rows",
        overlaps="pooches_for_sale_rows,vendor",
    )
