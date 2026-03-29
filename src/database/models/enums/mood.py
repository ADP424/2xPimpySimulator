from sqlalchemy.dialects.postgresql import ENUM

MOOD = ENUM(
    "happy",
    "excited",
    "sleepy",
    "grumpy",
    "anxious",
    "mischievous",
    "zoomies",
    "hungry",
    "content",
    "clingy",
    "dead",
    name="mood",
    create_type=True,
)
