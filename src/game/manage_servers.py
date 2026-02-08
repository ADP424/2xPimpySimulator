from typing import Optional
from database import (
    get_event_channel_id,
    set_event_channel_id,
)


async def get_event_channel(server_id: int) -> Optional[int]:
    event_channel_id = get_event_channel_id(server_id)
    return event_channel_id


async def set_event_channel(server_id: int, event_channel_id: int) -> Optional[int]:
    set_event_channel_id(server_id, event_channel_id)
