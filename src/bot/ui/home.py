from __future__ import annotations

import discord
from discord.ui import Button, Select, View

from src.bot.constants import VIEW_TIMEOUT
from src.bot.ui.util import (
    InteractionResponder,
    mention,
)
from src.game import get_or_create_owner

from .components import PaginatorView
from .graveyard import GraveyardPageSource
from .kennels import KennelsPageSource


async def build_home_content(guild_id: int, user_id: int) -> str:
    """
    Build home content.

    Parameters
    ----------
    guild_id: Any
        The `guild_id` value.

    user_id: Any
        The `user_id` value.

    Returns
    -------
    Any
        The result of calling `build_home_content`.
    """

    owner = await get_or_create_owner(guild_id, user_id)
    lines = [
        f"**{mention(owner.discord_id)}'s Home**",
        f"💵 **${owner.dollars}**",
        f"💀 **{owner.bloodskulls}** bloodskulls  🦴 **{owner.bones}** bones",
    ]

    # Body parts (only show if any are owned)
    def _int(attr: str) -> int:
        try:
            return int(getattr(owner, attr, 0) or 0)
        except TypeError, ValueError:
            return 0

    parts = {
        "❤️ hearts": _int("hearts"),
        "🧠 brains": _int("brains"),
        "👁️ eyes": _int("eyes"),
        "🦷 teeth": _int("teeth"),
        "🐾 tails": _int("tails"),
    }
    nonempty = [(label, count) for label, count in parts.items() if count > 0]
    if nonempty:
        lines.append("**Body Parts:** " + "  ".join(f"{label} ×{count}" for label, count in nonempty))
    return "\n".join(lines)


async def send_home_menu(interaction: discord.Interaction):
    """
    Send home menu.

    Parameters
    ----------
    interaction: Any
        The `interaction` value.

    Returns
    -------
    Any
        The result of calling `send_home_menu`.
    """

    r = InteractionResponder(interaction, ephemeral=False)
    if interaction.guild_id is None:
        await r.reply(content="This must be used in a server.")
        return
    content = await build_home_content(guild_id=interaction.guild_id, user_id=interaction.user.id)
    await r.reply(content=content, view=HomeView())


class HomeView(View):
    def __init__(self, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.add_item(HomeNavigationSelect())
        self.add_item(TownButton())


class HomeNavigationSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Navigate your home",
            options=[
                discord.SelectOption(label="Kennels", value="kennels"),
                discord.SelectOption(label="Graveyard", value="graveyard"),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)

        # Make sure the dropdown selection persists between refreshes
        for option in self.options:
            option.default = option.value == self.values[0]

        await r.edit(view=self.view)

        if self.values[0] == "kennels":
            source = KennelsPageSource(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            view = PaginatorView(source, owner_discord_id=interaction.user.id)
            content, embed = await view.build_first_page()
            await r.reply(
                content=content if content is not None else "Your kennels:",
                embed=embed,
                view=view,
            )

        if self.values[0] == "graveyard":
            source = GraveyardPageSource(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            view = PaginatorView(source, owner_discord_id=interaction.user.id)
            content, embed = await view.build_first_page()
            await r.reply(
                content=content if content is not None else "**Your Graveyard**",
                embed=embed,
                view=view,
            )


class TownButton(Button):
    def __init__(self):
        super().__init__(label="Town", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        from .town import TownView  # local import to dodge circular dependencies

        await r.reply(content="**Welcome to the Town**", view=TownView())
