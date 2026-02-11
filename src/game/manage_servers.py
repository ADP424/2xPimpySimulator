from typing import Optional
from database import (
    get_server_by_discord_id,
    create_server,
    get_event_channel_discord_id,
    set_event_channel_discord_id,
)
from .model import Server, to_server


async def get_or_create_server(server_id: int) -> Server:
    server = await get_server_by_discord_id(server_id)
    if server is None:
        server = await create_server(server_id)
    return to_server(server)


async def get_event_channel(server_id: int) -> Optional[int]:
    event_channel_discord_id = await get_event_channel_discord_id(server_id)
    return event_channel_discord_id


async def set_event_channel(server_id: int, event_channel_discord_id: int) -> Optional[int]:
    await set_event_channel_discord_id(server_id, event_channel_discord_id)
