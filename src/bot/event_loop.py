import discord

from src.bot.ui import send_triggered_event_dm
from src.logger import get_logger

logger = get_logger("bot/event_loop")


async def post_hourly_event_notifications(bot: discord.Client, triggered_owner_events: dict[int, list]):
    """
    Post hourly event notifications.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    triggered_owner_events: Any
        The `triggered_owner_events` value.

    Returns
    -------
    Any
        The result of calling `post_hourly_event_notifications`.
    """

    for owner_discord_id, events in triggered_owner_events.items():
        for event in events:
            delivered = await send_triggered_event_dm(bot, owner_discord_id, event)
            if not delivered:
                logger.warning(
                    "Failed to DM event %s to owner %s.",
                    getattr(event, "active_owner_event_id", "unknown"),
                    owner_discord_id,
                )
