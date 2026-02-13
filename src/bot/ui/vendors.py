import discord
from discord.ui import Select, Button, View
from typing import Optional

from bot.ui.util import edit_interaction
from game.model import Pooch, Vendor
from game import (
    buy_pooch,
    get_or_create_owner,
    get_or_create_server,
    get_pooch_price,
    list_server_vendors,
    list_vendor_pooches,
)

from .components.paginator import PageSource, PaginatorView
from .pooch_info import PoochInfoView


class VendorsPageSource(PageSource):
    def __init__(self, *, server_discord_id: int, owner_discord_id: int):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._vendors: list[Vendor] = []

    async def load(self):
        self._vendors = await list_server_vendors(self.server_discord_id)

    def page_count(self) -> int:
        return max(len(self._vendors), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._vendors:
            return None, discord.Embed(title="Vendors", description="There are no vendors in this server yet.")

        vendor = self._vendors[page_index]
        pooches = await list_vendor_pooches(vendor.id)

        embed = discord.Embed(title=vendor.name, description=f"{len(pooches)} pooches for sale")

        controls = VendorPageControls(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            vendor=vendor,
            pooches=pooches,
        )
        controls.attach(view)
        return None, embed


class VendorPageControls:
    def __init__(
        self,
        *,
        server_discord_id: int,
        owner_discord_id: int,
        vendor: Vendor,
        pooches: list[Pooch],
    ):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.vendor = vendor
        self.pooches = pooches
        self.selected_pooch: Optional[Pooch] = None

        if not pooches:
            options = [discord.SelectOption(label="No pooches for sale", value="__none__")]
        else:
            options = [
                discord.SelectOption(label=f"{pooch.name} (${get_pooch_price(pooch.id)})", value=str(pooch.id))
                for pooch in pooches
            ]

        self.select = Select(
            placeholder="Select a pooch",
            options=options,
            disabled=not bool(pooches),
        )
        self.select.callback = self._on_select  # type: ignore

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.buy_button = Button(label="Buy", style=discord.ButtonStyle.success, disabled=True)

        self.info_button.callback = self._on_info  # type: ignore
        self.buy_button.callback = self._on_buy  # type: ignore

        if not pooches:
            self.info_button.disabled = True
            self.buy_button.disabled = True

    def attach(self, view: View):
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.buy_button)

    async def _on_select(self, interaction: discord.Interaction):
        value = self.select.values[0]
        if value == "__none__":
            self.selected_pooch = None
            self.info_button.disabled = True
            self.buy_button.disabled = True
        else:
            selected_id = int(value)
            self.selected_pooch = next((pooch for pooch in self.pooches if pooch.id == selected_id), None)
            if self.selected_pooch is None:
                return
            self.info_button.disabled = False
            self.buy_button.disabled = False

        await edit_interaction(interaction, view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected_pooch is None:
            return
        server = await get_or_create_server(self.server_discord_id)
        owner = await get_or_create_owner(self.server_discord_id, self.owner_discord_id)
        view = PoochInfoView(server=server, pooch=self.selected_pooch, owner=owner)
        embed = await view.build_embed()
        await edit_interaction(interaction, embed=embed, view=view)

    async def _on_buy(self, interaction: discord.Interaction):
        if self.selected_pooch is None:
            return

        success, message = await buy_pooch(
            self.owner_discord_id,
            self.vendor.id,
            self.selected_pooch.id,
        )

        # If the purchase failed, tell the user why and keep the menu up.
        if not success:
            await interaction.response.send_message(message, ephemeral=True)
            return

        # Refresh the existing paginator message to reflect the updated stock.
        await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        if isinstance(interaction.view, PaginatorView):
            await interaction.view.refresh(interaction)
