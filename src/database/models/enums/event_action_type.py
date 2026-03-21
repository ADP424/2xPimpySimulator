from types import SimpleNamespace

# Plain list of valid action type strings.
# Validation is enforced at resource-load time by the Python validator.
# The database stores action_type as TEXT.
EVENT_ACTION_TYPE = SimpleNamespace(
    enums=[
        "modify_money",
        "modify_bloodskulls",
        "modify_pooch_health",
        "modify_pooch_age",
        "kill_pooch",
        "add_mutation",
        "remove_mutation",
        "add_breed",
        "remove_breed",
        "transfer_pooch",
        "create_pooch",
        "clone_pooch",
        "modify_kennel_capacity",
        "rename_pooch",
        "set_breeding_cooldown",
        "modify_breeding_cooldown",
        "modify_base_health",
        "set_pooch_age",
        "start_event",
        "breed_pooches",
        "sell_pooch",
        "buy_pooch",
        "release_stray",
        "receive_stray",
        "enter_kennel",
        "enter_vendor_stock",
        "start_stray_event",
        "start_server_event",
        "select_pooch",
        "revive_pooch",
        "damn_pooch",
        "conjure_pooch",
        "sacrifice_pooch",
        "fight_pooches",
    ]
)
