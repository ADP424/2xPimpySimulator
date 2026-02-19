import asyncio
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot.commands.get_money import register_get_money_command
from game import get_or_create_server
from logger import get_logger

from .commands.home import register_home_command
from .commands.set_event_channel import register_set_event_channel_command
from .commands.town import register_town_command
from .constants import GUILDS
from .day_change_loop import day_change_runner

logger = get_logger("bot/app")


def run():
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

    @bot.event
    async def on_ready():
        await tree.sync()
        for guild in GUILDS:
            await tree.sync(guild=guild)
            server = await get_or_create_server(guild.id)
            logger.info(f"Initialized Server with ID '{server.discord_id}'.")
        logger.info(f"Bot ready as {bot.user} ({stage})")

        if not hasattr(bot, "_day_change_task"):
            bot._day_change_task = asyncio.create_task(day_change_runner(bot, stage=stage, tz=tz))  # type: ignore

    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")

    bot.run(token)
