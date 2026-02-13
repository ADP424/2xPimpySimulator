from typing import Optional
from database import (
    get_server_by_discord_id,
    create_server,
    set_event_channel_discord_id,
)
from .model import Server, to_server


async def get_or_create_server(server_discord_id: int) -> Server:
    """
    Get a server with the given Discord ID.
    If no server with that ID exists yet, create it.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to get / create.

    Returns
    -------
    Server
        The Server with the given Discord ID.
    """

    server = await get_server_by_discord_id(server_discord_id)
    if server is None:
        server = await create_server(server_discord_id)
    return to_server(server)


async def get_event_channel(server_discord_id: int) -> Optional[int]:
    """
    Get the Discord ID of the event channel set for the given server.
    Returns None if no event channel has been set for the server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to get the event channel of.

    Returns
    -------
    int, optional
        The Discord ID of the event channel set for the server, or None if not found.
    """

    server = await get_server_by_discord_id(server_discord_id)
    if server is None:
        return None
    if server.event_channel_discord_id is not None:
        return server.event_channel_discord_id
    return None


async def set_event_channel(server_discord_id: int, event_channel_discord_id: int):
    """
    Set the Discord ID of the event channel for the given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to set the event channel of.

    event_channel_discord_id: int
        The channel Discord ID to set as the event channel for the server.
    """

    await set_event_channel_discord_id(server_discord_id, event_channel_discord_id)
