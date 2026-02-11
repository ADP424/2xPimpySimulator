from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from ..vendor import Vendor
    from ..pooch import Pooch


class VendorPoochForSale(Base):
    __tablename__ = "vendor_pooches_for_sale"

    pooch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pooches.id", ondelete="CASCADE"), primary_key=True)
    vendor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)

    pooch: Mapped[Pooch] = relationship(
        "Pooch",
        foreign_keys=[pooch_id],
        back_populates="vendor_pooch_for_sale_row",
    )
    vendor: Mapped[Vendor] = relationship(
        "Vendor",
        foreign_keys=[vendor_id],
        back_populates="pooches_for_sale_rows",
    )
