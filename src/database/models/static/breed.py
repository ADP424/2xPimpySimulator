from sqlalchemy import BigInteger, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base
from database.models.enums.rarity import RARITY


class Breed(Base):
    __tablename__ = "breeds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    alt_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))
