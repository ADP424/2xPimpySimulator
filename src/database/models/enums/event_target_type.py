from sqlalchemy.dialects.postgresql import ENUM

EVENT_TARGET_TYPE = ENUM(
    "owner",
    "pooch",
    "kennel",
    "server",
    name="event_target_type",
    create_type=False,
)
