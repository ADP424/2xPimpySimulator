from sqlalchemy.dialects.postgresql import ENUM

SIZE = ENUM(
    "tiny",
    "small",
    "average",
    "large",
    "massive",
    name="size",
    create_type=False,
)
