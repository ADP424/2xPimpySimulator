from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ...static.catalog.mutation import Mutation
    from ..entities import Vendor


class VendorDesiredMutation(Base):
    __tablename__ = "vendor_desired_mutations"
    __table_args__ = (
        UniqueConstraint("vendor_id", "mutation_id", name="vendor_desired_mutations_vendor_mutation_uniq"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    mutation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("mutations.id", ondelete="CASCADE"), nullable=False)

    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="desired_mutation_rows")
    mutation: Mapped[Mutation] = relationship("Mutation")
