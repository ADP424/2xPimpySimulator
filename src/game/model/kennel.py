from dataclasses import dataclass

from database.models.kennel import Kennel as KennelORM


@dataclass(frozen=True)
class Kennel:
    id: int
    server_id: int
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
        id=int(getattr(kennel, "id")),
        server_id=int(getattr(kennel, "server_id")),
        owner_discord_id=int(getattr(kennel, "owner_discord_id")),
        name=str(getattr(kennel, "name")),
        pooch_limit=int(getattr(kennel, "pooch_limit")),
    )
