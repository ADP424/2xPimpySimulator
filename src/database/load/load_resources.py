import asyncio

from src.database.load.load_resources import (
    load_injuries,
    load_owner_events,
    load_server_events,
    main,
)

__all__ = [
    "load_breeds",
    "load_mutations",
    "load_injuries",
    "load_dog_names",
    "load_vendor_first_names",
    "load_vendor_last_names",
    "load_owner_events",
    "load_server_events",
    "main",
    "validate_breeds_json",
    "validate_mutations_json",
    "load_names_from_root",
    "validate_name_list",
    "iter_files",
]


if __name__ == "__main__":
    asyncio.run(main())

from .breeds import load_breeds, validate_breeds_json
from .dog_names import load_dog_names
from .mutations import load_mutations, validate_mutations_json
from .utils import iter_files, load_names_from_root, validate_name_list
from .vendor_first_names import load_vendor_first_names
from .vendor_last_names import load_vendor_last_names
