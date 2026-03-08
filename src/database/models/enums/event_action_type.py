from sqlalchemy.dialects.postgresql import ENUM

EVENT_ACTION_TYPE = ENUM(
    "modify_money",
    "modify_bloodskulls",
    "modify_pooch_health",
    "modify_pooch_age",
    "kill_pooch",
    "add_mutation",
    "remove_mutation",
    "add_breed",
    "transfer_pooch",
    "create_pooch",
    "modify_kennel_capacity",
    "rename_pooch",
    "set_breeding_cooldown",
    "start_event",
    name="event_action_type",
    create_type=False,
)
