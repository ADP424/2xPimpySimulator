from dataclasses import dataclass

from database.models import Server as ServerORM


@dataclass(frozen=True)
class Server:
    server_id: int
    event_channel_id: int


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
        server_id=int(getattr(server, "server_id")),
        event_channel_id=int(
            getattr(server, "event_channel_id"),
        ),
    )
