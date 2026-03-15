from __future__ import annotations

import discord
from discord.ui import Button, View

from src.bot.constants import VIEW_TIMEOUT
from src.bot.ui.util import InteractionResponder
from src.game import visit_park
from src.logger import get_logger

logger = get_logger("bot/ui/park")


class ParkView(View):
    """Town Park."""

    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

        self.add_item(_AttractStrayButton(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))
        self.add_item(_TownButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id


class _TownButton(Button):
    def __init__(self):
        super().__init__(label="Town", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        from .town import TownView  # local import to dodge circular dependencies

        await r.reply(content="**Welcome to the Town**", view=TownView())


class _AttractStrayButton(Button):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(label="Attract a Stray", style=discord.ButtonStyle.primary, row=0)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        await r.defer(thinking=True)

        try:
            caught, message = await visit_park(
                server_discord_id=self.server_discord_id,
                owner_discord_id=self.owner_discord_id,
            )
        except Exception as exception:
            logger.error(f"Error during park visit: '{exception}'")
            await r.finish_with_error("Something went wrong at the park.")
            return

        prefix = "✅ " if caught else ""
        await r.reply(content=f"{prefix}{message}")
