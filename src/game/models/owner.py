from dataclasses import dataclass

from database.models import Owner as OwnerORM


@dataclass(frozen=True)
class Owner:
    discord_id: int
    discord_name: str | None
    dollars: int
    bloodskulls: int


async def to_owner(owner: OwnerORM) -> Owner:
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

    return Owner(
        discord_id=owner.discord_id,
        discord_name=owner.discord_name,
        dollars=owner.dollars,
        bloodskulls=owner.bloodskulls,
    )
