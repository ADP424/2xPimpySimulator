from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import Server as ServerORM


SEASONS = ("spring", "summer", "autumn", "winter")


@dataclass(frozen=True)
class Server:
    discord_id: int
    event_channel_discord_id: int
    current_season: str = "spring"


async def to_server(server: ServerORM) -> Server:
    """
    Convert an ORM Server object to a game Server object.

    Parameters
    ----------
    server: Server
        The Server object to convert.

    Returns
    -------
    Server
        The converted Server dataclass object.
    """

    return Server(
        discord_id=server.discord_id,
        event_channel_discord_id=server.event_channel_discord_id,
        current_season=getattr(server, "current_season", None) or "spring",
    )
