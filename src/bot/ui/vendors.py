from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.database import (
    get_owner_by_discord_id,
    give_money_to_owner,
    give_owner_item,
    list_items_by_category,
)
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

from .components import (
    PageSource,
    PaginatorView,
    build_breed_info_embed,
    build_mutation_info_embed,
)
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

        desired_names = [m.name for m in vendor.desired_mutations]
        embed.add_field(
            name="Desired Mutations",
            value=("\n".join([f"• {n}" for n in desired_names]) if desired_names else "—"),
            inline=True,
        )

        desired_breed_names = [f"{b.name} ({b.rarity})" for b in vendor.desired_breeds]
        embed.add_field(
            name="Desired Breeds",
            value=("\n".join([f"• {n}" for n in desired_breed_names]) if desired_breed_names else "—"),
            inline=True,
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

        self._desired_mutations = vendor.desired_mutations
        if not self._desired_mutations:
            mutation_options = [discord.SelectOption(label="No desired mutations", value="__none__")]
        else:
            mutation_options = [discord.SelectOption(label=m.name, value=str(m.id)) for m in self._desired_mutations]

        self.mutation_select = Select(
            placeholder="Vendor desired mutation...",
            options=mutation_options,
            disabled=not bool(self._desired_mutations),
            min_values=1,
            max_values=1,
        )
        self.mutation_select.callback = self._on_mutation_select

        self._desired_breeds = vendor.desired_breeds
        if not self._desired_breeds:
            breed_options = [discord.SelectOption(label="No desired breeds", value="__none__")]
        else:
            breed_options = [
                discord.SelectOption(label=f"{b.name} ({b.rarity})", value=str(b.id)) for b in self._desired_breeds
            ]

        self.breed_select = Select(
            placeholder="Vendor desired breed...",
            options=breed_options,
            disabled=not bool(self._desired_breeds),
            min_values=1,
            max_values=1,
        )
        self.breed_select.callback = self._on_breed_select

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
        self.items_button = Button(label="🛒 Buy Items", style=discord.ButtonStyle.secondary)

        self.info_button.callback = self._on_info
        self.buy_button.callback = self._on_buy
        self.sell_button.callback = self._on_sell
        self.items_button.callback = self._on_buy_items

        if not pooches:
            self.info_button.disabled = True
            self.buy_button.disabled = True

    def attach(self, view: View):
        # Row 0 is reserved for paginator nav buttons.
        self.mutation_select.row = 1
        self.breed_select.row = 2
        self.select.row = 3
        self.info_button.row = 4
        self.buy_button.row = 4
        self.sell_button.row = 4
        self.items_button.row = 4

        view.add_item(self.mutation_select)
        view.add_item(self.breed_select)
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.buy_button)
        view.add_item(self.sell_button)
        view.add_item(self.items_button)

    async def _on_mutation_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.mutation_select.values[0]
        if value == "__none__":
            return
        mutation_id = int(value)
        mutation = next((m for m in self._desired_mutations if m.id == mutation_id), None)
        if mutation is None:
            return

        for opt in self.mutation_select.options:
            opt.default = opt.value == value

        await r.edit(view=self.mutation_select.view)
        await r.reply(embed=build_mutation_info_embed(mutation))

    async def _on_breed_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.breed_select.values[0]
        if value == "__none__":
            return
        breed_id = int(value)
        breed = next((b for b in self._desired_breeds if b.id == breed_id), None)
        if breed is None:
            return

        for opt in self.breed_select.options:
            opt.default = opt.value == value

        await r.edit(view=self.breed_select.view)
        await r.reply(embed=build_breed_info_embed(breed))

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

    async def _on_buy_items(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        re = InteractionResponder(interaction, ephemeral=True)
        cleaning = await list_items_by_category("cleaning")
        food = await list_items_by_category("food")
        all_items = cleaning + food
        if not all_items:
            await re.reply(content="This vendor has no items for sale.")
            return
        view = _BuyItemsView(owner_discord_id=self.owner_discord_id, items=all_items)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)


class _BuyItemsView(View):
    """Simple view for buying consumable items from a vendor."""

    def __init__(self, owner_discord_id: int, items: list):
        from src.bot.constants import VIEW_TIMEOUT

        super().__init__(timeout=VIEW_TIMEOUT)
        self._owner_id = owner_discord_id
        self._items = items
        self._selected_item = None

        from src.bot.constants import DISCORD_SELECT_MAX_OPTIONS

        options = [
            discord.SelectOption(
                label=f"{item.name} (${(item.parameters or {}).get('price', 10)})",
                value=item.name,
                description=(item.description or "")[:100],
            )
            for item in items[:DISCORD_SELECT_MAX_OPTIONS]
        ]
        select = Select(placeholder="Select an item to buy", options=options)
        select.callback = self._on_select
        self._select = select
        self.add_item(select)

        self._buy_btn = Button(label="Buy ×1", style=discord.ButtonStyle.success, disabled=True, row=1)
        self._buy_btn.callback = self._on_buy
        self.add_item(self._buy_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def build_embed(self) -> discord.Embed:
        lines = []
        for item in self._items:
            price = (item.parameters or {}).get("price", 10)
            units = (item.parameters or {}).get("food_units", 0)
            reduction = (item.parameters or {}).get("mess_reduction", 0)
            detail = f"${price}"
            if units:
                detail += f" · {units} food units"
            if reduction:
                detail += f" · −{reduction} mess"
            lines.append(f"**{item.name}** — {detail}")
        embed = discord.Embed(title="🛒 Items for Sale", description="\n".join(lines))
        return embed

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        item_name = self._select.values[0]
        self._selected_item = next((i for i in self._items if i.name == item_name), None)
        self._buy_btn.disabled = self._selected_item is None
        for opt in self._select.options:
            opt.default = opt.value == item_name
        await r.edit(view=self)

    async def _on_buy(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        if self._selected_item is None:
            return
        item = self._selected_item
        price = int((item.parameters or {}).get("price", 10))
        owner = await get_owner_by_discord_id(self._owner_id)
        if owner is None or owner.dollars < price:
            await re.reply(content=f"Not enough money. Cost: ${price}")
            return
        await give_money_to_owner(self._owner_id, -price)
        await give_owner_item(self._owner_id, item.name, 1)
        await re.reply(content=f"✅ Purchased **{item.name}** for **${price}**.")


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
