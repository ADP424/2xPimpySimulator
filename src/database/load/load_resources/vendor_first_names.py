from sqlalchemy import delete

from src.logger import get_logger

from ...models import VendorFirstName
from ...session import session_scope
from .utils import (
    VENDOR_NAMES_ROOT,
    load_names_from_root,
    validate_name_list,
)

logger = get_logger("database/load/load_resources/vendor_first_names")

VENDOR_FIRST_NAMES_ROOT = VENDOR_NAMES_ROOT / "first"


async def load_vendor_first_names():
    logger.info("Loading vendor first names from 'resources/vendor_names/first/**/*.txt' into the database...")

    vendor_first_names = validate_name_list("vendor_first_names", load_names_from_root(VENDOR_FIRST_NAMES_ROOT))

    async with session_scope() as session:
        await session.execute(delete(VendorFirstName))

        for vendor_first_name in vendor_first_names:
            session.add(VendorFirstName(name=vendor_first_name))

    logger.info("Finished loading vendor first names.")
