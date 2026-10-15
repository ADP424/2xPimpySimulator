from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.database import (
    create_server,
    get_server_by_discord_id,
)
from src.database import list_servers as db_list_servers
from src.database import (
    set_event_channel_discord_id,
)

from .models import to_server

if TYPE_CHECKING:
    from .models import Server


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


async def get_server(server_discord_id: int) -> Optional[Server]:
    """
    Get the server with the given Discord ID, without creating it.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to get.

    Returns
    -------
    Server, optional
        The Server, or None if the bot has never registered it.
    """

    server = await get_server_by_discord_id(server_discord_id)
    if server is None:
        return None
    return await to_server(server)


async def list_servers() -> list[Server]:
    """
    List every server the bot has registered.

    Returns
    -------
    list[Server]
        All known servers.
    """

    return [await to_server(server) for server in await db_list_servers()]


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
    return await to_server(server)


async def list_all_servers() -> list[Server]:
    """Return all registered servers."""
    return await list_servers()


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
