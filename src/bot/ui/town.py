import discord
from discord.ui import Button, Select, View

from src.bot.constants import VIEW_TIMEOUT
from src.bot.ui.util import InteractionResponder

from .church import ChurchView
from .marketplace import MarketplaceView
from .park import ParkView
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
                discord.SelectOption(label="Marketplace", value="marketplace"),
                discord.SelectOption(label="Veterinary Clinic", value="vet"),
                discord.SelectOption(label="Church", value="church"),
                discord.SelectOption(label="Park", value="park"),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        for option in self.options:
            option.default = option.value == self.values[0]
        await r.edit(view=self.view)

        if self.values[0] == "marketplace":
            view = MarketplaceView(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            await r.reply(content="**Marketplace**", view=view)

        if self.values[0] == "vet":
            view = VetClinicView(owner_discord_id=interaction.user.id)
            await r.reply(content="Welcome to the town vet!", view=view)

        if self.values[0] == "church":
            view = ChurchView(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            await r.reply(content="**Welcome to the Church**", view=view)

        if self.values[0] == "park":
            view = ParkView(server_discord_id=interaction.guild_id, owner_discord_id=interaction.user.id)
            await r.reply(content="**Welcome to the Park**", view=view)


class HomeButton(Button):
    def __init__(self):
        super().__init__(label="Home", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        from .home import send_home_menu  # local import to dodge circular dependencies

        # send_home_menu replies; it does not need a defer for fast actions.
        await send_home_menu(interaction)
