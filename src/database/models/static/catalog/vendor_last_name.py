from __future__ import annotations

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base


class VendorLastName(Base):
    __tablename__ = "vendor_last_names"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
