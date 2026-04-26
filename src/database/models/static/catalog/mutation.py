from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base
from ...enums import HEALTH_IMPACT, RARITY


class Mutation(Base):
    __tablename__ = "mutations"
    __table_args__ = (CheckConstraint("heritability BETWEEN 0 AND 1", name="bounded_heritability"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    alt_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    heritability: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("0.25")
    )

    health_impact: Mapped[str] = mapped_column(HEALTH_IMPACT, nullable=False, server_default=text("'neutral'"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))

    affects_females: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    affects_males: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    parameters: Mapped[dict[str, str | int | float | list[str]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    invisible_messages: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    reveal_chance: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("1.0")
    )
