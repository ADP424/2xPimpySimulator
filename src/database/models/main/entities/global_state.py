from __future__ import annotations

from sqlalchemy import BigInteger, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base


class GlobalState(Base):
    __tablename__ = "global_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    current_season: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'spring'"))
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Absolute hours since game start. current_day = current_hour // 24. This
    # is the authoritative hour counter for the hourly change loop.
    current_hour: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"), default=0)
