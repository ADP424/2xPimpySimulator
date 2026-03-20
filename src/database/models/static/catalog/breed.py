from sqlalchemy import BigInteger, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base
from ...enums import RARITY


class Breed(Base):
    __tablename__ = "breeds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    alt_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))
    min_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("8"))
    max_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("12"))

    parameters: Mapped[dict[str, str | int | float | list[str]]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
