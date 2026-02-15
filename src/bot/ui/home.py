import discord
from discord.ui import View, Select

from bot.ui.util import edit_interaction

from .kennels import KennelsPageSource
from .vendors import VendorsPageSource
from .components.paginator import PaginatorView


class HomeView(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(NavigationSelect())


class NavigationSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Where do you want to go?",
            options=[
                discord.SelectOption(label="Kennels", value="kennels"),
                discord.SelectOption(label="Vendors", value="vendors"),
                discord.SelectOption(label="Town", value="town"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "kennels":
            source = KennelsPageSource(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            view = PaginatorView(source, owner_discord_id=interaction.user.id)
            await edit_interaction(interaction, content="Your kennels:", embed=None, view=view)
            await view.start(interaction)
        elif self.values[0] == "vendors":
            source = VendorsPageSource(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            view = PaginatorView(source, owner_discord_id=interaction.user.id)
            await edit_interaction(interaction, content="Vendor stalls:", embed=None, view=view)
            await view.start(interaction)
        else:
            await interaction.response.send_message("Town coming soon.", ephemeral=False)
