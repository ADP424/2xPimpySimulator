import asyncio
import os

import discord

from src.game import run_hourly_event_check
from src.logger import get_logger

from .constants import EVENT_LOOP_INTERVAL_SECONDS
from .ui.events import send_triggered_event_dm

logger = get_logger("bot/event_loop")


async def post_hourly_event_notifications(bot: discord.Client, triggered_owner_events: dict[int, list]):
    for owner_discord_id, events in triggered_owner_events.items():
        for event in events:
            delivered = await send_triggered_event_dm(bot, owner_discord_id, event)
            if not delivered:
                logger.warning(
                    "Failed to DM event %s to owner %s.",
                    getattr(event, "active_owner_event_id", "unknown"),
                    owner_discord_id,
                )


async def hourly_event_runner(bot: discord.Client, stage: str):
    async def run_once():
        logger.info("Running hourly event check...")
        triggered_events = await run_hourly_event_check(rng_seed=int.from_bytes(os.urandom(8)))
        await post_hourly_event_notifications(bot, triggered_events)

    bot._hourly_event_run_once = run_once

    logger.info("Beginning hourly event loop...")
    while True:
        sleep_seconds = 60.0 if stage == "dev" else EVENT_LOOP_INTERVAL_SECONDS
        await asyncio.sleep(sleep_seconds)
        try:
            await run_once()
        except Exception as exception:
            logger.exception(f"Hourly event check failed: {exception}")
            if stage == "dev":
                raise exception
