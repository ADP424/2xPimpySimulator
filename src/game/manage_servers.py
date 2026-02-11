from typing import Optional
from database import (
    get_server_by_discord_id,
    create_server,
    set_event_channel_discord_id,
)
from .model import Server, to_server


async def get_or_create_server(server_id: int) -> Server:
    server = await get_server_by_discord_id(server_id)
    if server is None:
        server = await create_server(server_id)
    return to_server(server)


async def get_event_channel(server_id: int) -> Optional[int]:
    server = await get_server_by_discord_id(server_id)
    if server is None:
        return None
    channel_id = getattr(server, "event_channel_discord_id", None)
    if channel_id is not None:
        return int(channel_id)
    return None


async def set_event_channel(server_id: int, event_channel_discord_id: int) -> Optional[int]:
    await set_event_channel_discord_id(server_id, event_channel_discord_id)
