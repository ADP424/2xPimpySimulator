import os
import discord
from discord import app_commands
from dotenv import load_dotenv

from logger import get_logger

from .commands.home import register_home_command

logger = get_logger("bot/app")

GUILDS = [discord.Object(id=1267910656838078474)]


def run():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    stage = os.getenv("STAGE", "dev").lower()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Client(intents=intents)
    tree = app_commands.CommandTree(bot)

    register_home_command(tree)

    @bot.event
    async def on_ready():
        for guild in GUILDS:
            await tree.sync(guild=guild)
        print(f"Bot ready as {bot.user} ({stage})")

    if not token:
        raise RuntimeError("DISCORD_TOKEN not set")
    bot.run(token)
