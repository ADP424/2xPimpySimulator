import asyncio
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot.commands.get_money import register_get_money_command
from bot.commands.increment_day import register_increment_day_command
from bot.commands.pause_day_loop import register_pause_day_loop_command
from game import get_or_create_server
from logger import get_logger

from .commands.home import register_home_command
from .commands.set_event_channel import register_set_event_channel_command
from .commands.town import register_town_command
from .constants import GUILDS
from .day_change_loop import _fetch_and_update_names, day_change_runner

logger = get_logger("bot/app")


def run(update_names_only: bool = False, skip_startup_day_change: bool = False):
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

    # dev only commands
    if stage == "dev":
        register_get_money_command(tree)
        register_pause_day_loop_command(tree)
        register_increment_day_command(tree)

    @bot.event
    async def on_ready():
        if stage == "dev":
            for guild in GUILDS:
                try:
                    await tree.sync(guild=guild)
                except discord.Forbidden:
                    logger.warning(f"Cannot sync commands to guild {guild.id} (missing access)")
        else:
            await tree.sync()
        for guild in GUILDS:
            server = await get_or_create_server(guild.id)
            logger.info(f"Initialized Server with ID '{server.discord_id}'.")
        logger.info(f"Bot ready as {bot.user} ({stage})")

        if update_names_only:
            await _fetch_and_update_names(bot)
            await bot.close()
            return

        if not hasattr(bot, "_day_change_task"):
            bot._day_change_task = asyncio.create_task(day_change_runner(bot, stage=stage, tz=tz, skip_startup_day_change=skip_startup_day_change))  # type: ignore

    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")

    bot.run(token)
