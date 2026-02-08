import discord
from discord.ui import Select, Button, View
from typing import Optional

from bot.ui.util import edit_interaction
from game.model import Kennel, Pooch

from .components.paginator import PageSource
from .pooch_info import PoochInfoView

from game import list_owner_kennels, list_kennel_pooches


class KennelsPageSource(PageSource):
    def __init__(self, *, server_id: int, owner_discord_id: int):
        self.server_id = server_id
        self.owner_discord_id = owner_discord_id
        self._kennels: list[Kennel] = []

    async def load(self):
        self._kennels = await list_owner_kennels(self.server_id, self.owner_discord_id)

    def page_count(self) -> int:
        return max(len(self._kennels), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._kennels:
            return None, discord.Embed(title="Kennels", description="You don't have any kennels yet.")

        kennel = self._kennels[page_index]
        pooches = await list_kennel_pooches(self.server_id, kennel.id)

        embed = discord.Embed(title=kennel.name, description=f"{len(pooches)} / {kennel.pooch_limit} pooches")

        controls = KennelPageControls(server_id=self.server_id, owner_id=self.owner_discord_id, pooches=pooches)
        controls.attach(view)
        return None, embed


class KennelPageControls:
    def __init__(self, *, server_id: int, owner_id: int, pooches: list[Pooch]):
        self.server_id = server_id
        self.owner_id = owner_id
        self.pooches = pooches
        self.selected_pooch_id: Optional[int] = None

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

        self.info_btn = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.breed_btn = Button(label="Breed", style=discord.ButtonStyle.secondary, disabled=True)
        self.walk_btn = Button(label="Walk", style=discord.ButtonStyle.secondary, disabled=True)

        self.info_btn.callback = self._on_info  # type: ignore
        self.breed_btn.callback = self._noop  # type: ignore
        self.walk_btn.callback = self._noop  # type: ignore

        if not pooches:
            self.info_btn.disabled = True
            self.breed_btn.disabled = True
            self.walk_btn.disabled = True

    def attach(self, view: View):
        view.add_item(self.select)
        view.add_item(self.info_btn)
        view.add_item(self.breed_btn)
        view.add_item(self.walk_btn)

    async def _on_select(self, interaction: discord.Interaction):
        self.selected_pooch_id = int(self.select.values[0])
        self.info_btn.disabled = False
        self.breed_btn.disabled = False
        self.walk_btn.disabled = False
        await edit_interaction(interaction, view=interaction.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected_pooch_id is None:
            return
        view = PoochInfoView(server_id=self.server_id, pooch_id=self.selected_pooch_id, owner_id=self.owner_id)
        embed = await view.build_embed()
        await edit_interaction(interaction, embed=embed, view=view)

    async def _noop(self, interaction: discord.Interaction):
        await interaction.response.send_message("Coming soon.", ephemeral=False)
