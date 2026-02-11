from dataclasses import dataclass

from database.models import Server as ServerORM


@dataclass(frozen=True)
class Server:
    id: int
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

    event_channel_discord_id = getattr(server, "event_channel_discord_id")
    if event_channel_discord_id is not None:
        event_channel_discord_id = int(event_channel_discord_id)

    return Server(
        id=int(getattr(server, "id")),
        event_channel_discord_id=event_channel_discord_id,
    )
