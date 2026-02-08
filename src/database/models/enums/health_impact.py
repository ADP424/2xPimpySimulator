from sqlalchemy.dialects.postgresql import ENUM

HEALTH_IMPACT = ENUM(
    "instant_death",
    "fatal",
    "brutal",
    "severe",
    "unhealthy",
    "harmful",
    "neutral",
    "helpful",
    "healthy",
    "great",
    "fantastic",
    "brilliant",
    "immortality",
    name="health_impact",
    create_type=False,
)
