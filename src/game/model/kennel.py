from dataclasses import dataclass

from database.models import Kennel as KennelORM


@dataclass(frozen=True)
class Kennel:
    id: int
    owner_discord_id: int
    name: str
    pooch_limit: int


def to_kennel(kennel: KennelORM) -> Kennel:
    """
    Convert an ORM Kennel object to a game Kennel object.

    Parameters
    ----------
    kennel: Kennel
        The Kennel object to convert.

    Returns
    -------
    Kennel
        The converted Kennel dataclass object.
    """

    return Kennel(
        id=kennel.id,
        owner_discord_id=kennel.owner_discord_id,
        name=kennel.name,
        pooch_limit=kennel.pooch_limit,
    )
