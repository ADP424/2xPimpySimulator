from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.game import (
    buy_pooch,
    get_or_create_owner,
    get_or_create_server,
    get_pooch_buy_price,
    get_pooch_sell_price,
    list_kennel_pooches,
    list_owner_kennels,
    list_server_vendors,
    list_vendor_pooches,
    sell_pooch,
)
from src.logger import get_logger

if TYPE_CHECKING:
    from src.game.models import Kennel, Pooch, Vendor

from .components import PageSource, PaginatorView, build_mutation_info_embed
from .pooch_info import PoochInfoView
from .util import InteractionResponder

logger = get_logger("bot/ui/vendors")


class VendorsMenuView(View):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        from src.bot.constants import VIEW_TIMEOUT

        super().__init__(timeout=VIEW_TIMEOUT)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id


class VendorsPageSource(PageSource):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
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

        desired = [vendor.desired_mutation_1, vendor.desired_mutation_2, vendor.desired_mutation_3]
        desired_names = [m.name for m in desired if m is not None]
        embed.add_field(
            name="Desired Mutations",
            value=("\n".join([f"• {n}" for n in desired_names]) if desired_names else "—"),
            inline=False,
        )

        prices_by_pooch_id: dict[int, int] = {}
        for pooch in pooches:
            prices_by_pooch_id[pooch.id] = await get_pooch_buy_price(pooch.id, vendor.id)

        controls = VendorPageControls(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            vendor=vendor,
            pooches=pooches,
            prices_by_pooch_id=prices_by_pooch_id,
        )
        controls.attach(view)
        return None, embed


class VendorPageControls:
    def __init__(
        self,
        server_discord_id: int,
        owner_discord_id: int,
        vendor: Vendor,
        pooches: list[Pooch],
        prices_by_pooch_id: dict[int, int],
    ):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.vendor = vendor
        self.pooches = pooches
        self.selected_pooch: Optional[Pooch] = None

        desired = [vendor.desired_mutation_1, vendor.desired_mutation_2, vendor.desired_mutation_3]
        self._desired_mutations = [m for m in desired if m is not None]
        if not self._desired_mutations:
            mutation_options = [discord.SelectOption(label="No desired mutations", value="__none__")]
        else:
            mutation_options = [discord.SelectOption(label=m.name, value=str(m.id)) for m in self._desired_mutations]

        # A select-only control (no extra buttons) so it can coexist with the pooch select.
        self.mutation_select = Select(
            placeholder="Vendor desired mutation...",
            options=mutation_options,
            disabled=not bool(self._desired_mutations),
            min_values=1,
            max_values=1,
        )
        self.mutation_select.callback = self._on_mutation_select

        if not pooches:
            options = [discord.SelectOption(label="No pooches for sale", value="__none__")]
        else:
            options = [
                discord.SelectOption(
                    label=f"{pooch.name} (${prices_by_pooch_id.get(pooch.id, 0)})",
                    value=str(pooch.id),
                )
                for pooch in pooches
            ]

        self.select = Select(
            placeholder="Select a pooch",
            options=options,
            disabled=not bool(pooches),
        )
        self.select.callback = self._on_select

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.buy_button = Button(label="Buy", style=discord.ButtonStyle.success, disabled=True)
        self.sell_button = Button(label="Sell Pooch", style=discord.ButtonStyle.secondary)

        self.info_button.callback = self._on_info
        self.buy_button.callback = self._on_buy
        self.sell_button.callback = self._on_sell

        if not pooches:
            self.info_button.disabled = True
            self.buy_button.disabled = True

    def attach(self, view: View):
        # Row 0 is reserved for paginator nav buttons.
        self.mutation_select.row = 1

        self.select.row = 2
        self.info_button.row = 3
        self.buy_button.row = 3
        self.sell_button.row = 4

        view.add_item(self.mutation_select)
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.buy_button)
        view.add_item(self.sell_button)

    async def _on_mutation_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.mutation_select.values[0]
        if value == "__none__":
            return
        mutation_id = int(value)
        mutation = next((m for m in self._desired_mutations if m.id == mutation_id), None)
        if mutation is None:
            return

        # Persist selection.
        for opt in self.mutation_select.options:
            opt.default = opt.value == value

        await r.edit(view=self.mutation_select.view)
        await r.reply(embed=build_mutation_info_embed(mutation))

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.select.values[0]
        if value == "__none__":
            self.selected_pooch = None
            self.info_button.disabled = True
            self.buy_button.disabled = True
            for option in self.select.options:
                option.default = False
        else:
            selected_id = int(value)
            self.selected_pooch = next((pooch for pooch in self.pooches if pooch.id == selected_id), None)
            if self.selected_pooch is None:
                return
            self.info_button.disabled = False
            self.buy_button.disabled = False

            # Make sure the dropdown selection persists between refreshes
            for option in self.select.options:
                option.default = option.value == str(selected_id)

        await r.edit(view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_pooch is None:
            return
        server = await get_or_create_server(self.server_discord_id)
        owner = await get_or_create_owner(self.server_discord_id, self.owner_discord_id)
        view = PoochInfoView(server=server, pooch=self.selected_pooch, owner=owner)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_buy(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_pooch is None:
            return
        await r.defer(thinking=True)

        try:
            success, message = await buy_pooch(
                self.owner_discord_id,
                self.vendor.id,
                self.selected_pooch.id,
            )
        except Exception as exception:
            logger.error(f"Error buying pooch: '{exception}'")
            await r.finish_with_error("Purchase failed unexpectedly.")
            return

        if not success:
            await r.reply(content=message)
            return
        parent_view = self.select.view
        if isinstance(parent_view, PaginatorView):
            await parent_view.refresh(interaction)
        else:
            await r.edit(view=parent_view)

        await r.reply(content=f"✅ {message}")

    async def _on_sell(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = _SellKennelsPageSource(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            vendor=self.vendor,
        )
        view = PaginatorView(source, owner_discord_id=self.owner_discord_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class _SellKennelsPageSource(PageSource):
    def __init__(self, server_discord_id: int, owner_discord_id: int, vendor: Vendor):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.vendor = vendor
        self._kennels: list[Kennel] = []

    async def load(self):
        self._kennels = await list_owner_kennels(self.owner_discord_id)

    def page_count(self) -> int:
        return max(len(self._kennels), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._kennels:
            return (
                f"**Sell to {self.vendor.name}**",
                discord.Embed(title="Sell Pooch", description="You don't have any kennels yet."),
            )

        kennel = self._kennels[page_index]
        pooches = [p for p in (await list_kennel_pooches(kennel.id)) if p.alive]

        embed = discord.Embed(
            title=f"Sell to {self.vendor.name} — {kennel.name}",
            description=f"Choose a pooch to sell. ({len(pooches)} living in this kennel)",
        )

        prices: dict[int, int] = {}
        for pooch in pooches:
            prices[pooch.id] = await get_pooch_sell_price(pooch.id, self.vendor.id)

        controls = _SellKennelControls(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            vendor=self.vendor,
            pooches=pooches,
            prices_by_pooch_id=prices,
        )
        controls.attach(view)

        return f"**Sell to {self.vendor.name}**", embed


class _SellKennelControls:
    def __init__(
        self,
        server_discord_id: int,
        owner_discord_id: int,
        vendor: Vendor,
        pooches: list[Pooch],
        prices_by_pooch_id: dict[int, int],
    ):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.vendor = vendor
        self.pooches = pooches
        self.prices_by_pooch_id = prices_by_pooch_id
        self.selected_pooch: Optional[Pooch] = None

        if not pooches:
            options = [discord.SelectOption(label="No living pooches in this kennel", value="__none__")]
        else:
            options = [
                discord.SelectOption(
                    label=f"{p.name} (${prices_by_pooch_id.get(p.id, 0)})",
                    value=str(p.id),
                )
                for p in pooches
            ]

        self.select = Select(placeholder="Select a pooch to sell", options=options, disabled=not bool(pooches))
        self.select.callback = self._on_select

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.sell_button = Button(label="Sell", style=discord.ButtonStyle.danger, disabled=True)

        self.info_button.callback = self._on_info
        self.sell_button.callback = self._on_sell

    def attach(self, view: View):
        self.select.row = 1
        self.info_button.row = 2
        self.sell_button.row = 2
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.sell_button)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.select.values[0]
        if value == "__none__":
            self.selected_pooch = None
            self.info_button.disabled = True
            self.sell_button.disabled = True
            for option in self.select.options:
                option.default = False
        else:
            selected_id = int(value)
            self.selected_pooch = next((p for p in self.pooches if p.id == selected_id), None)
            if self.selected_pooch is None:
                return
            self.info_button.disabled = False
            self.sell_button.disabled = False
            for option in self.select.options:
                option.default = option.value == value

        await r.edit(view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_pooch is None:
            return
        server = await get_or_create_server(self.server_discord_id)
        owner = await get_or_create_owner(self.server_discord_id, self.owner_discord_id)
        view = PoochInfoView(server=server, pooch=self.selected_pooch, owner=owner)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_sell(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_pooch is None:
            return
        await r.defer(thinking=True)

        try:
            success, message = await sell_pooch(self.owner_discord_id, self.vendor.id, self.selected_pooch.id)
        except Exception as exception:
            logger.error(f"Error selling pooch: '{exception}'")
            await r.finish_with_error("Sale failed unexpectedly.")
            return

        if not success:
            await r.reply(content=message)
            return

        parent_view = self.select.view
        if isinstance(parent_view, PaginatorView):
            await parent_view.refresh(interaction)
        else:
            await r.edit(view=parent_view)

        await r.reply(content=f"✅ {message}")
