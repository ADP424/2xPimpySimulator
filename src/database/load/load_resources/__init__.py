from .breeds import load_breeds, validate_breeds_json
from .dog_names import load_dog_names
from .injuries import load_injuries
from .mutations import load_mutations, validate_mutations_json
from .owner_events import load_owner_events
from .server_events import load_server_events
from .stray_events import load_stray_events
from .utils import (
    BaseEventValidator,
    EventValidationError,
    ResourceValidationError,
    load_names_from_root,
    validate_name_list,
)
from .vendor_first_names import load_vendor_first_names
from .vendor_last_names import load_vendor_last_names


async def main():
    """
    Main.

    Returns
    -------
    Any
        The result of calling `main`.
    """

    from .utils import logger

    logger.info("Loading resources into database...")
    await load_breeds()
    await load_mutations()
    await load_injuries()
    await load_dog_names()
    await load_vendor_first_names()
    await load_vendor_last_names()
    await load_owner_events()
    await load_server_events()
    await load_stray_events()
    logger.info("Finished loading resources into database.")


__all__ = [
    "load_breeds",
    "validate_breeds_json",
    "load_mutations",
    "validate_mutations_json",
    "load_injuries",
    "load_dog_names",
    "load_vendor_first_names",
    "load_vendor_last_names",
    "load_owner_events",
    "load_server_events",
    "load_stray_events",
    "BaseEventValidator",
    "EventValidationError",
    "ResourceValidationError",
    "load_names_from_root",
    "validate_name_list",
    "main",
]
