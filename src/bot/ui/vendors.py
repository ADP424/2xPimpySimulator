import discord
from discord.ui import Select, Button, View
from typing import Optional

from bot.ui.util import edit_interaction
from game.model import Vendor, Pooch
from game import list_server_vendors, list_vendor_pooches, buy_pooch, get_price

from .components.paginator import PageSource, PaginatorView
from .pooch_info import PoochInfoView


class VendorsPageSource(PageSource):
    def __init__(self, *, server_id: int, owner_discord_id: int):
        self.server_id = server_id
        self.owner_discord_id = owner_discord_id
        self._vendors: list[Vendor] = []

    async def load(self):
        self._vendors = await list_server_vendors(self.server_id)

    def page_count(self) -> int:
        return max(len(self._vendors), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._vendors:
            return None, discord.Embed(title="Vendors", description="There are no vendors in this server yet.")

        vendor = self._vendors[page_index]
        pooches = await list_vendor_pooches(self.server_id, vendor.id)

        embed = discord.Embed(title=vendor.name, description=f"{len(pooches)} pooches for sale")

        controls = VendorPageControls(
            server_id=self.server_id,
            owner_id=self.owner_discord_id,
            vendor_id=vendor.id,
            pooches=pooches,
        )
        controls.attach(view)
        return None, embed


class VendorPageControls:
    def __init__(
        self,
        *,
        server_id: int,
        owner_id: int,
        vendor_id: int,
        pooches: list[Pooch],
    ):
        self.server_id = server_id
        self.owner_id = owner_id
        self.vendor_id = vendor_id
        self.pooches = pooches
        self.selected_pooch_id: Optional[int] = None

        if not pooches:
            options = [discord.SelectOption(label="No pooches for sale", value="__none__")]
        else:
            options = [discord.SelectOption(label=f"{p.name} (${get_price(p.id)})", value=str(p.id)) for p in pooches]

        self.select = Select(
            placeholder="Select a pooch",
            options=options,
            disabled=not bool(pooches),
        )
        self.select.callback = self._on_select  # type: ignore

        self.info_btn = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.buy_btn = Button(label="Buy", style=discord.ButtonStyle.success, disabled=True)

        self.info_btn.callback = self._on_info  # type: ignore
        self.buy_btn.callback = self._on_buy  # type: ignore

        if not pooches:
            self.info_btn.disabled = True
            self.buy_btn.disabled = True

    def attach(self, view: View):
        view.add_item(self.select)
        view.add_item(self.info_btn)
        view.add_item(self.buy_btn)

    async def _on_select(self, interaction: discord.Interaction):
        val = self.select.values[0]
        if val == "__none__":
            self.selected_pooch_id = None
            self.info_btn.disabled = True
            self.buy_btn.disabled = True
        else:
            self.selected_pooch_id = int(val)
            self.info_btn.disabled = False
            self.buy_btn.disabled = False

        await edit_interaction(interaction, view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected_pooch_id is None:
            return
        view = PoochInfoView(server_id=self.server_id, pooch_id=self.selected_pooch_id, owner_id=self.owner_id)
        embed = await view.build_embed()
        await edit_interaction(interaction, embed=embed, view=view)

    async def _on_buy(self, interaction: discord.Interaction):
        if self.selected_pooch_id is None:
            return

        ok, message = await buy_pooch(
            server_id=self.server_id,
            owner_discord_id=self.owner_id,
            vendor_id=self.vendor_id,
            pooch_id=self.selected_pooch_id,
        )

        # If the purchase failed, tell the user why and keep the menu up.
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return

        # Success: refresh the existing paginator message to reflect the updated stock.
        await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        if isinstance(interaction.view, PaginatorView):
            await interaction.view.refresh(interaction)
