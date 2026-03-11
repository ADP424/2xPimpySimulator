from sqlalchemy import delete

from src.logger import get_logger

from ...models import VendorLastName
from ...session import session_scope
from .utils import (
    VENDOR_NAMES_ROOT,
    load_names_from_root,
    validate_name_list,
)

logger = get_logger("database/load/load_resources/vendor_last_names")

VENDOR_LAST_NAMES_ROOT = VENDOR_NAMES_ROOT / "last"


async def load_vendor_last_names():
    logger.info("Loading vendor last names from 'resources/vendor_names/last/**/*.txt' into the database...")

    vendor_last_names = validate_name_list("vendor_last_names", load_names_from_root(VENDOR_LAST_NAMES_ROOT))

    async with session_scope() as session:
        await session.execute(delete(VendorLastName))

        for vendor_last_name in vendor_last_names:
            session.add(VendorLastName(name=vendor_last_name))

    logger.info("Finished loading vendor last names.")
