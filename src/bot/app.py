import os
import asyncio
import discord
from discord import app_commands
from dotenv import load_dotenv

from logger import get_logger

from game import get_or_create_server
from .commands.home import register_home_command
from .commands.set_event_channel import register_set_event_channel_command
from .day_change_loop import day_change_runner

logger = get_logger("bot/app")

GUILDS = [discord.Object(id=1267910656838078474)]


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
    register_set_event_channel_command(tree)

    @bot.event
    async def on_ready():
        for guild in GUILDS:
            await tree.sync(guild=guild)
            server = await get_or_create_server(guild.id)
            logger.info(f"Initialized Server with ID '{server.id}'.")
        logger.info(f"Bot ready as {bot.user} ({stage})")

        if not hasattr(bot, "_day_change_task"):
            bot._day_change_task = asyncio.create_task(day_change_runner(bot, stage=stage, tz=tz))  # type: ignore

    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")

    bot.run(token)
