import asyncio
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from src.bot.commands import (
    register_event_history_command,
    register_get_money_command,
    register_home_command,
    register_increment_day_command,
    register_pause_day_loop_command,
    register_pending_events_command,
    register_server_event_command,
    register_set_event_channel_command,
    register_town_command,
    register_trigger_event_command,
)
from src.bot.ui import register_active_server_event_views
from src.game import get_or_create_server
from src.logger import get_logger

from .constants import GUILDS
from .day_change_loop import (
    day_change_runner,
    fetch_and_update_names,
    week_change_runner,
)
from .event_loop import hourly_event_runner

logger = get_logger("bot/app")


def run(update_names_only: bool = False, skip_startup_day_change: bool = False):
    """
    Run.

    Parameters
    ----------
    update_names_only: Any
        The `update_names_only` value.

    skip_startup_day_change: Any
        The `skip_startup_day_change` value.

    Returns
    -------
    Any
        The result of calling `run`.
    """

    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    stage = os.getenv("STAGE", "dev").lower()
    tz = os.getenv("TZ", "America/New_York")

    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Client(intents=intents)
    tree = app_commands.CommandTree(bot)

    register_home_command(tree)
    register_town_command(tree)
    register_set_event_channel_command(tree)
    register_event_history_command(tree)
    register_pending_events_command(tree)
    register_server_event_command(tree)

    if stage == "dev":
        register_get_money_command(tree)
        register_pause_day_loop_command(tree)
        register_increment_day_command(tree)
        register_trigger_event_command(tree)

    async def sync_commands():
        if stage == "dev":
            for guild in GUILDS:
                tree.copy_global_to(guild=guild)
                await tree.sync(guild=guild)
                logger.info(f"Synced commands to guild {guild.id}")
        else:
            await tree.sync()
            logger.info("Synced global commands")

    @bot.event
    async def setup_hook():
        await sync_commands()

    @bot.event
    async def on_ready():
        for guild in GUILDS:
            server = await get_or_create_server(guild.id)
            logger.info(f"Initialized Server with ID '{server.discord_id}'.")

        await register_active_server_event_views(bot)

        logger.info(f"Bot ready as {bot.user} ({stage})")

        if update_names_only:
            await fetch_and_update_names(bot)
            await bot.close()
            return

        if not hasattr(bot, "_day_change_task"):
            bot._day_change_task = asyncio.create_task(day_change_runner(bot, stage=stage, tz=tz))
        if not hasattr(bot, "_week_change_task"):
            bot._week_change_task = asyncio.create_task(week_change_runner(bot, stage=stage))
        if not hasattr(bot, "_hourly_event_task"):
            bot._hourly_event_task = asyncio.create_task(hourly_event_runner(bot, stage=stage))

    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")

    bot.run(token)
