from __future__ import annotations

from sqlalchemy import Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base


class GlobalState(Base):
    __tablename__ = "global_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    current_season: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'spring'"))
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
