from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.database.models.enums.rarity import RARITY


class RarityWeight(Base):
    __tablename__ = "rarity_weights"

    rarity: Mapped[str] = mapped_column(RARITY, primary_key=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
