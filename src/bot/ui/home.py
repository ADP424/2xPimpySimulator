import discord
from discord.ui import View, Select, Button

from game import get_or_create_owner
from bot.ui.util import edit_interaction, mention, reply_to_interacted_message

from .kennels import KennelsPageSource
from .components.paginator import PaginatorView


async def build_home_content(*, guild_id: int, user_id: int) -> str:
    owner = await get_or_create_owner(guild_id, user_id)
    return (
        f"**{mention(owner.discord_id)}'s Home**\n"
        f"You have ${owner.dollars}.\n"
        f"You have {owner.bloodskulls} bloodskulls."
    )


async def send_home_menu(interaction: discord.Interaction):
    if interaction.guild_id is None:
        await reply_to_interacted_message(interaction, content="This must be used in a server.")
        return
    content = await build_home_content(guild_id=interaction.guild_id, user_id=interaction.user.id)
    await reply_to_interacted_message(interaction, content=content, view=HomeView())


class HomeView(View):
    def __init__(self, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.add_item(HomeNavigationSelect())
        self.add_item(TownButton())


class HomeNavigationSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Navigate your home",
            options=[
                discord.SelectOption(label="Kennels", value="kennels"),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):

        # Make sure the dropdown selection persists between refreshes
        for option in self.options:
            option.default = option.value == self.values[0]

        await edit_interaction(interaction, view=self.view)

        if self.values[0] == "kennels":
            source = KennelsPageSource(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            view = PaginatorView(source, owner_discord_id=interaction.user.id)
            content, embed = await view.build_first_page()
            await reply_to_interacted_message(
                interaction,
                content=content if content is not None else "Your kennels:",
                embed=embed,
                view=view,
            )


class TownButton(Button):
    def __init__(self):
        super().__init__(label="Town", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        from .town import TownView  # local import to dodge circular dependencies

        await reply_to_interacted_message(
            interaction,
            content="**Welcome to the Town**",
            view=TownView(),
        )
