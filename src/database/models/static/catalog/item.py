"""
Item catalog model.

Loaded from ``resources/items/<category>/*.jsonc`` at startup. Categories
cover cleaning products, dog food, and any future consumables. Parameters
are a free-form JSONB blob whose keys depend on category:

- ``cleaning``: ``price``, ``mess_reduction``, optional ``side_effect_health`` (applied to every pooch in the kennel)
- ``food``: ``price``, ``food_units``, optional ``<stat>_add`` stat bonuses (a chance per feeding)
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ... import Base
from ...enums import RARITY


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    alt_name: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    rarity: Mapped[str] = mapped_column(RARITY, nullable=False, server_default=text("'common'"))

    parameters: Mapped[dict[str, str | int | float | list[str]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
