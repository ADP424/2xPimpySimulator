from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base
from ...enums import HEALTH_IMPACT


class Disease(Base):
    __tablename__ = "diseases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    health_impact: Mapped[str] = mapped_column(HEALTH_IMPACT, nullable=False)

    contagion_chance: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("0.0")
    )
    sexually_transmitted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    recovery_chance: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("0.0")
    )
    treatable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    curable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    immunity_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    heritability: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("0.0")
    )

    seasons: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    season_contagion_modifiers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    invisible_messages: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    reveal_chance: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("1.0")
    )
