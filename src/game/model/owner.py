from dataclasses import dataclass

from database.models.owner import Owner as OwnerORM


@dataclass(frozen=True)
class Owner:
    server_id: int
    discord_id: int


def to_owner(owner: OwnerORM) -> Owner:
    """
    Convert an ORM Owner object to a game Owner object.

    Parameters
    ----------
    owner: Owner
        The Owner object to convert.

    Returns
    -------
    Owner
        The converted Owner dataclass object.
    """

    return Owner(server_id=int(getattr(owner, "server_id")), discord_id=int(getattr(owner, "discord_id")))
