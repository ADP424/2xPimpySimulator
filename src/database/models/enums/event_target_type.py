from sqlalchemy.dialects.postgresql import ENUM

EVENT_TARGET_TYPE = ENUM(
    "owner",
    "pooch",
    "kennel",
    "all_pooches",
    "all_kennels",
    name="event_target_type",
    create_type=False,
)
