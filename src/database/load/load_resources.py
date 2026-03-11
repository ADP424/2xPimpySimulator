import asyncio

from src.database.load.load_resources import (
    load_breeds,
    load_dog_names,
    load_mutations,
    load_owner_events,
    load_server_events,
    load_vendor_first_names,
    load_vendor_last_names,
    main,
)

__all__ = [
    "load_breeds",
    "load_mutations",
    "load_dog_names",
    "load_vendor_first_names",
    "load_vendor_last_names",
    "load_owner_events",
    "load_server_events",
    "main",
]


if __name__ == "__main__":
    asyncio.run(main())
