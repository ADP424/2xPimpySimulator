from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base
from database.models.enums.health_impact import HEALTH_IMPACT


class HealthImpactWeight(Base):
    __tablename__ = "health_impact_weights"

    health_impact: Mapped[str] = mapped_column(HEALTH_IMPACT, primary_key=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
