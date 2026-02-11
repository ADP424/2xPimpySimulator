import random
from typing import Optional

from database.models.enums.sex import SEX
from sqlalchemy import cast, delete, func, or_, select

from .session import session_scope

from .models import *  # loads all ORM models (via database/models/__init__.py)


async def list_servers() -> list[Server]:
    """
    Fetch a list of all servers in the database.

    Returns
    -------
    list[Server]
        The list of all Server ORM objects in the database.
    """

    async with session_scope() as session:
        query = select(Server)
        response = await session.execute(query)

    return list(response.scalars().all())


async def get_server_by_discord_id(server_discord_id: int) -> Optional[Server]:
    """
    Fetch a server by its Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The ID of the server to fetch.

    Returns
    -------
    Server, optional
        The Server ORM object, or None if no server with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Server).where(Server.discord_id == server_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def create_server(server_discord_id: int) -> Server:
    """
    Create a server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to create.

    Returns
    -------
    Server
        The Server ORM object just created.
    """

    async with session_scope() as session:
        server = Server(discord_id=server_discord_id)
        session.add(server)
        await session.flush()

    return server


async def set_event_channel_discord_id(server_discord_id: int, channel_discord_id: int) -> Optional[Server]:
    """
    Set the channel for automated events to be sent to for the server with the given Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The ID of the server to set the event channel of.

    channel_discord_id: int
        The Discord ID of the channel to send automated events for the server to.

    Returns
    -------
    Server, optional
        The Server object the event channel Discord ID was set for, or None if no server with the given Discord ID was found.
    """

    async with session_scope() as session:
        server = await session.get(Server, {"id": server_discord_id})

    if server is not None:
        server.event_channel_discord_id = channel_discord_id

    return server
