from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base
from ...enums import EVENT_SEVERITY, HEALTH_IMPACT


class Injury(Base):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    health_impact: Mapped[str] = mapped_column(HEALTH_IMPACT, nullable=False)
    severity: Mapped[str] = mapped_column(EVENT_SEVERITY, nullable=False, server_default=text("'minor'"))
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    treated: Mapped[dict] = mapped_column(JSONB, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    invisible_messages: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    reveal_chance: Mapped[float] = mapped_column(
        Numeric(4, 3, asdecimal=False), nullable=False, server_default=text("1.0")
    )
