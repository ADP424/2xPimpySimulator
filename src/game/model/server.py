from dataclasses import dataclass

from database.models import Server as ServerORM


@dataclass(frozen=True)
class Server:
    discord_id: int
    event_channel_discord_id: int


def to_server(server: ServerORM) -> Server:
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
    )
