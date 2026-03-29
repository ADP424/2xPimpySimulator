from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ...static.catalog.breed import Breed
    from ..entities import Vendor


class VendorDesiredBreed(Base):
    __tablename__ = "vendor_desired_breeds"
    __table_args__ = (UniqueConstraint("vendor_id", "breed_id", name="vendor_desired_breeds_vendor_breed_uniq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    breed_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("breeds.id", ondelete="CASCADE"), nullable=False)

    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="desired_breed_rows")
    breed: Mapped[Breed] = relationship("Breed")
