import discord
from discord.ui import Button, Select, View

from bot.constants import VIEW_TIMEOUT
from bot.ui.util import defer_interaction, edit_interaction, reply_to_interacted_message

from .components.paginator import PaginatorView
from .vendors import VendorsPageSource
from .vet_clinic import VetClinicView


class TownView(View):
    def __init__(self, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.add_item(TownNavigationSelect())
        self.add_item(HomeButton())


class TownNavigationSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Navigate the Town",
            options=[
                discord.SelectOption(label="Vendors", value="vendors"),
                discord.SelectOption(label="Veterinary Clinic", value="vet"),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        for option in self.options:
            option.default = option.value == self.values[0]
        await edit_interaction(interaction, view=self.view)

        if self.values[0] == "vendors":
            source = VendorsPageSource(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            view = PaginatorView(source, owner_discord_id=interaction.user.id)
            content, embed = await view.build_first_page()
            await reply_to_interacted_message(
                interaction,
                content=content if content is not None else "**Vendor Stalls**",
                embed=embed,
                view=view,
            )

        if self.values[0] == "vet":
            view = VetClinicView(owner_discord_id=interaction.user.id)
            await reply_to_interacted_message(interaction, content="Welcome to the town vet!", view=view)


class HomeButton(Button):
    def __init__(self):
        super().__init__(label="Home", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        from .home import send_home_menu  # local import to dodge circular dependencies

        await send_home_menu(interaction)
