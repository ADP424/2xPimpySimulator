from typing import Optional

import discord
from discord.ui import Button, Select, View

from bot.ui.util import edit_interaction, reply_to_interacted_message
from game import (
    get_or_create_owner,
    get_or_create_server,
    list_kennel_pooches,
    list_owner_kennels,
)
from game.models import Kennel, Pooch

from .breeding import BreedMateView
from .components.paginator import PageSource
from .pooch_info import PoochInfoView


class KennelsPageSource(PageSource):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._kennels: list[Kennel] = []

    async def load(self):
        self._kennels = await list_owner_kennels(self.owner_discord_id)

    def page_count(self) -> int:
        return max(len(self._kennels), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._kennels:
            return None, discord.Embed(title="Kennels", description="You don't have any kennels yet.")

        kennel = self._kennels[page_index]
        pooches = await list_kennel_pooches(kennel.id)

        embed = discord.Embed(title=kennel.name, description=f"{len(pooches)} / {kennel.pooch_limit} pooches")

        controls = KennelPageControls(
            server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id, pooches=pooches
        )
        controls.attach(view)
        return None, embed


class KennelPageControls:
    def __init__(self, server_discord_id: int, owner_discord_id: int, pooches: list[Pooch]):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.pooches = pooches
        self.selected_pooch: Optional[Pooch] = None

        if not pooches:
            options = [discord.SelectOption(label="No pooches in this kennel", value="__none__")]
        else:
            options = [discord.SelectOption(label=pooch.name, value=str(pooch.id)) for pooch in pooches]

        self.select = Select(
            placeholder="Select a pooch",
            options=options,
            disabled=not bool(pooches),
        )

        self.select.callback = self._on_select  # type: ignore

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.breed_button = Button(label="Breed", style=discord.ButtonStyle.secondary, disabled=True)
        self.walk_button = Button(label="Walk", style=discord.ButtonStyle.secondary, disabled=True)

        self.info_button.callback = self._on_info  # type: ignore
        self.breed_button.callback = self._on_breed  # type: ignore
        self.walk_button.callback = self._noop  # type: ignore

        if not pooches:
            self.info_button.disabled = True
            self.breed_button.disabled = True
            self.walk_button.disabled = True

    def attach(self, view: View):
        self.select.row = 1
        self.info_button.row = 2
        self.breed_button.row = 2
        self.walk_button.row = 2

        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.breed_button)
        view.add_item(self.walk_button)

    async def _on_select(self, interaction: discord.Interaction):
        selected_id = int(self.select.values[0])
        self.selected_pooch = next((pooch for pooch in self.pooches if pooch.id == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False
        self.breed_button.disabled = False
        self.walk_button.disabled = False

        # Make sure the dropdown selection persists between refreshes
        for option in self.select.options:
            option.default = option.value == str(selected_id)

        await edit_interaction(interaction, view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected_pooch is None:
            return
        server = await get_or_create_server(self.server_discord_id)
        owner = await get_or_create_owner(self.server_discord_id, self.owner_discord_id)
        view = PoochInfoView(server=server, pooch=self.selected_pooch, owner=owner)
        embed = await view.build_embed()
        await reply_to_interacted_message(interaction, embed=embed, view=view)

    async def _on_breed(self, interaction: discord.Interaction):
        if self.selected_pooch is None:
            return

        pooch = self.selected_pooch
        mates = [mate for mate in self.pooches if mate.id != pooch.id and mate.sex != pooch.sex]

        if not mates:
            await reply_to_interacted_message(
                interaction, content="There are no valid mates in this kennel for that pooch."
            )
            return

        view = BreedMateView(pooch=pooch, mates=mates)
        await reply_to_interacted_message(interaction, content="Select a mate:", view=view)

    async def _noop(self, interaction: discord.Interaction):
        await interaction.response.send_message("Coming soon.", ephemeral=False)
