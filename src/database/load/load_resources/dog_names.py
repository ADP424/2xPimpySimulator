from sqlalchemy import delete

from src.database.session import session_scope
from src.logger import get_logger

from ...models import DogName
from .utils import (
    RESOURCE_ROOT,
    load_names_from_root,
    validate_name_list,
)

logger = get_logger("database/load/load_resources/dog_names")

_DOG_NAMES_ROOT = RESOURCE_ROOT / "dog_names"


async def load_dog_names():
    """
    Load dog names.

    Returns
    -------
    Any
        The result of calling `load_dog_names`.
    """

    logger.info(f"Loading dog names from '{_DOG_NAMES_ROOT}/**/*.txt' into the database...")

    dog_names = validate_name_list("dog_names", load_names_from_root(_DOG_NAMES_ROOT))

    async with session_scope() as session:
        await session.execute(delete(DogName))

        for dog_name in dog_names:
            session.add(DogName(name=dog_name))

    logger.info("Finished loading dog names.")
