from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base


class VendorFirstName(Base):
    __tablename__ = "vendor_first_names"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
