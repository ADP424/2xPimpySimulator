"""
Owner-owned consumable item inventory (cleaning products, dog food, etc.).

A generic key-value inventory. ``item_name`` refers to an ``Item`` catalog
row by name (items are loaded from ``resources/items/<category>/*.jsonc``).
``count`` is the owned quantity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base

if TYPE_CHECKING:
    from ..entities import Owner


class OwnerItem(Base):
    __tablename__ = "owner_items"
    __table_args__ = (CheckConstraint("count >= 0", name="owner_item_count_minimum"),)

    owner_discord_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("owners.discord_id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_name: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    owner: Mapped[Owner] = relationship("Owner", foreign_keys=[owner_discord_id])
