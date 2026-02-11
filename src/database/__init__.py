from .kennel_manager import (
    list_pooches_for_kennel,
    get_kennel_by_id,
    get_pooch_kennel,
    create_kennel,
    add_pooch_to_kennel,
    remove_pooch_from_kennel,
)

from .owner_manager import (
    list_kennels_for_owner,
    get_owner_by_discord_id,
    create_owner,
    give_money_to_owner,
    add_owner_to_server,
    bury_pooch,
)

from .pooch_manager import (
    list_living_pooches,
    list_pooch_children,
    list_pooch_siblings,
    list_pooch_pregnancies,
    get_pooch_by_id,
    get_pooch_parents,
    create_pooch,
    age_pooch,
    decrement_pooch_breeding_cooldown,
    set_pooch_dead,
    delete_pregnancy,
)

from .server_manager import (
    list_servers,
    get_server_by_discord_id,
    create_server,
    set_event_channel_discord_id,
)

from .vendor_manager import (
    list_vendors,
    list_vendor_pooch_stock,
    get_vendor_by_id,
    create_vendor,
    add_pooch_to_vendor_stock,
    clear_vendor_pooch_stock,
    remove_pooch_from_vendor_stock,
)

__all__ = [
    # Kennel manager
    "list_pooches_for_kennel",
    "get_kennel_by_id",
    "create_kennel",
    "get_pooch_kennel",
    "add_pooch_to_kennel",
    "remove_pooch_from_kennel",
    # Owner manager
    "list_kennels_for_owner",
    "get_owner_by_discord_id",
    "create_owner",
    "give_money_to_owner",
    "add_owner_to_server",
    "bury_pooch",
    # Pooch manager
    "list_living_pooches",
    "get_pooch_by_id",
    "create_pooch",
    "decrement_pooch_breeding_cooldown",
    "age_pooch",
    "set_pooch_dead",
    "get_pooch_parents",
    "list_pooch_children",
    "list_pooch_siblings",
    "list_pooch_pregnancies",
    "delete_pregnancy",
    # Server manager
    "list_servers",
    "get_server_by_discord_id",
    "create_server",
    "set_event_channel_discord_id",
    # Vendor manager
    "list_vendors",
    "list_vendor_pooch_stock",
    "get_vendor_by_id",
    "create_vendor",
    "add_pooch_to_vendor_stock",
    "clear_vendor_pooch_stock",
    "remove_pooch_from_vendor_stock",
]
