from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.constants import MAX_NAME_LENGTH
from src.bot.ui.util import InteractionResponder
from src.game import (
    cast_out_pooch,
    clean_kennel_by_hand,
    clean_kennel_with_item,
    feed_kennel,
    get_breeding_chance,
    get_or_create_owner,
    get_or_create_server,
    get_owner_inventory,
    list_items,
    list_kennel_pooches,
    list_owner_kennels,
    rename_kennel,
    rename_pooch,
)
from src.game.utils.obfuscation import messiness_label

if TYPE_CHECKING:
    from src.game.models import Kennel, Pooch

from .breeding import BreedMateView
from .components import PageSource, PaginatorView
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

        food_stock = getattr(kennel, "food_stock", 0)
        embed = discord.Embed(
            title=kennel.name,
            description=(
                f"{len(pooches)} / {kennel.pooch_limit} pooches\n"
                f"🧹 Messiness: **{messiness_label(kennel.messiness, capacity=kennel.pooch_limit)}**\n"
                f"🍖 Food stock: **{food_stock}** units"
            ),
        )

        controls = KennelPageControls(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            kennel=kennel,
            pooches=pooches,
        )
        controls.attach(view)
        return None, embed


class KennelPageControls:
    def __init__(self, server_discord_id: int, owner_discord_id: int, kennel: Kennel, pooches: list[Pooch]):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.kennel = kennel
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

        self.select.callback = self._on_select

        self.rename_kennel_button = Button(label="Rename", style=discord.ButtonStyle.secondary)
        self.clean_kennel_button = Button(label="Clean", style=discord.ButtonStyle.primary)
        self.show_clean_button = kennel.messiness > 0
        self.rename_kennel_button.callback = self._on_rename_kennel
        self.clean_kennel_button.callback = self._on_clean_kennel

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.breed_button = Button(label="Breed", style=discord.ButtonStyle.secondary, disabled=True)
        self.walk_button = Button(label="Walk", style=discord.ButtonStyle.secondary, disabled=True)
        self.rename_pooch_button = Button(label="Rename Pooch", style=discord.ButtonStyle.secondary, disabled=True)
        self.cast_out_button = Button(label="Cast Out", style=discord.ButtonStyle.danger, disabled=True)

        self.feed_button = Button(label="🍖 Feed", style=discord.ButtonStyle.secondary)
        self.feed_button.callback = self._on_feed

        self.info_button.callback = self._on_info
        self.breed_button.callback = self._on_breed
        self.walk_button.callback = self._noop
        self.rename_pooch_button.callback = self._on_rename_pooch
        self.cast_out_button.callback = self._on_cast_out

        if not pooches:
            self.info_button.disabled = True
            self.breed_button.disabled = True
            self.walk_button.disabled = True
            self.rename_pooch_button.disabled = True
            self.cast_out_button.disabled = True

    def attach(self, view: View):
        self.rename_kennel_button.row = 0
        self.clean_kennel_button.row = 0
        self.feed_button.row = 0
        self.select.row = 1
        self.info_button.row = 2
        self.breed_button.row = 2
        self.walk_button.row = 2
        self.rename_pooch_button.row = 2
        self.cast_out_button.row = 3

        view.add_item(self.rename_kennel_button)
        if self.show_clean_button:
            view.add_item(self.clean_kennel_button)
        view.add_item(self.feed_button)
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.breed_button)
        view.add_item(self.walk_button)
        view.add_item(self.rename_pooch_button)
        view.add_item(self.cast_out_button)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        selected_id = self.select.values[0]
        self.selected_pooch = next((pooch for pooch in self.pooches if str(pooch.id) == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False
        self.breed_button.disabled = False
        self.walk_button.disabled = False
        self.rename_pooch_button.disabled = False
        self.cast_out_button.disabled = False

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

    async def _on_breed(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_pooch is None:
            return

        pooch = self.selected_pooch
        mates = [mate for mate in self.pooches if mate.id != pooch.id and mate.sex != pooch.sex]

        if not mates:
            await r.reply(content="There are no valid mates in this kennel for that pooch.")
            return

        view = BreedMateView(pooch=pooch, mates=mates, chance=await get_breeding_chance(pooch.id))
        await r.reply(content="Select a mate:", view=view)

    async def _noop(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        await r.reply(content="Coming soon.")

    async def _on_rename_kennel(self, interaction: discord.Interaction):
        # Modals must be shown through the raw interaction response.
        parent_view = self.select.view
        if parent_view is None:
            return
        await interaction.response.send_modal(
            _RenameKennelModal(
                owner_discord_id=self.owner_discord_id,
                kennel_id=self.kennel.id,
                current_name=self.kennel.name,
                parent_view=parent_view,
            )
        )

    async def _on_clean_kennel(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        # Open item selection view
        cleaning_items = await list_items("cleaning")
        owned = await get_owner_inventory(self.owner_discord_id)
        view = _CleanKennelView(
            owner_discord_id=self.owner_discord_id,
            kennel_id=self.kennel.id,
            cleaning_items=cleaning_items,
            owned=owned,
            parent_view=self.select.view,
        )
        embed = view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_feed(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        food_items = await list_items("food")
        owned = await get_owner_inventory(self.owner_discord_id)
        food_stock = getattr(self.kennel, "food_stock", 0)
        view = _FeedKennelView(
            owner_discord_id=self.owner_discord_id,
            kennel_id=self.kennel.id,
            food_items=food_items,
            owned=owned,
            food_stock=food_stock,
            parent_view=self.select.view,
        )
        embed = view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_rename_pooch(self, interaction: discord.Interaction):
        if self.selected_pooch is None:
            return
        parent_view = self.select.view
        if parent_view is None:
            return
        await interaction.response.send_modal(
            _RenamePoochModal(
                owner_discord_id=self.owner_discord_id,
                pooch_id=self.selected_pooch.id,
                current_name=self.selected_pooch.name,
                parent_view=parent_view,
            )
        )

    async def _on_cast_out(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_pooch is None:
            return
        success, message = await cast_out_pooch(self.owner_discord_id, self.selected_pooch.id, self.server_discord_id)
        if not success:
            await r.reply(content=message)
            return

        parent_view = self.select.view
        if isinstance(parent_view, PaginatorView):
            await parent_view.refresh(interaction)

        await r.reply(content=message)


class _RenameKennelModal(discord.ui.Modal):
    def __init__(self, owner_discord_id: int, kennel_id: int, current_name: str, parent_view: View):
        super().__init__(title="Rename Kennel")
        self._owner_id = owner_discord_id
        self._kennel_id = kennel_id
        self._parent_view = parent_view

        self.name = discord.ui.TextInput(
            label="New kennel name",
            placeholder=current_name[: MAX_NAME_LENGTH - 1] if current_name else "e.g. The Bloodhound Barn",
            min_length=1,
            max_length=MAX_NAME_LENGTH,
            required=True,
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if interaction.user.id != self._owner_id:
            await r.reply(content="That's not your kennel.")
            return

        new_name = str(self.name.value).strip()
        ok = await rename_kennel(self._kennel_id, new_name)
        if not ok:
            await r.reply(content=f"That name is too long. Keep it under {MAX_NAME_LENGTH} characters.")
            return

        # Refresh the current page so the new name shows up immediately.
        if isinstance(self._parent_view, PaginatorView):
            await self._parent_view.refresh(interaction)

        await r.reply(content=f"✅ Renamed kennel to **{new_name}**")


class _RenamePoochModal(discord.ui.Modal):
    def __init__(self, owner_discord_id: int, pooch_id: int, current_name: str, parent_view: View):
        super().__init__(title="Rename Pooch")
        self._owner_id = owner_discord_id
        self._pooch_id = pooch_id
        self._parent_view = parent_view

        self.name = discord.ui.TextInput(
            label="New pooch name",
            placeholder=current_name[: MAX_NAME_LENGTH - 1] if current_name else "e.g. Meatball",
            min_length=1,
            max_length=MAX_NAME_LENGTH,
            required=True,
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if interaction.user.id != self._owner_id:
            await r.reply(content="That's not your pooch.")
            return

        new_name = str(self.name.value).strip()
        ok = await rename_pooch(self._pooch_id, new_name)
        if not ok:
            await r.reply(content=f"That name is too long. Keep it under {MAX_NAME_LENGTH} characters.")
            return

        if isinstance(self._parent_view, PaginatorView):
            await self._parent_view.refresh(interaction)

        await r.reply(content=f"✅ Renamed pooch to **{new_name}**")


class _CleanKennelView(View):
    def __init__(self, owner_discord_id: int, kennel_id: int, cleaning_items: list, owned: dict, parent_view: View):
        from src.bot.constants import VIEW_TIMEOUT

        super().__init__(timeout=VIEW_TIMEOUT)
        self._owner_id = owner_discord_id
        self._kennel_id = kennel_id
        self._cleaning_items = cleaning_items
        self._owned = owned
        self._parent_view = parent_view

        options = [discord.SelectOption(label="Hand Clean (free, once/day)", value="hand")]
        for item in cleaning_items:
            count = owned.get(item.name, 0)
            reduction = (item.parameters or {}).get("mess_reduction", 0)
            label = f"{item.name} (−{reduction} mess, {count} owned)"
            options.append(discord.SelectOption(label=label[:100], value=item.name, description=f"Owned: {count}"))

        select = Select(placeholder="Choose a cleaning method", options=options[:25])
        select.callback = self._on_select
        self.add_item(select)
        self._select = select

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🧹 Clean Kennel", description="Choose a cleaning method.")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def _on_select(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        choice = self._select.values[0]
        if choice == "hand":
            ok, msg = await clean_kennel_by_hand(self._owner_id, self._kennel_id)
        else:
            ok, msg = await clean_kennel_with_item(self._owner_id, self._kennel_id, choice)
        if not ok:
            await re.reply(content=f"❌ {msg}")
            return
        if isinstance(self._parent_view, PaginatorView):
            await self._parent_view.refresh(interaction)
        await re.reply(content=f"✅ {msg}")


class _FeedKennelView(View):
    def __init__(
        self, owner_discord_id: int, kennel_id: int, food_items: list, owned: dict, food_stock: int, parent_view: View
    ):
        from src.bot.constants import VIEW_TIMEOUT

        super().__init__(timeout=VIEW_TIMEOUT)
        self._owner_id = owner_discord_id
        self._kennel_id = kennel_id
        self._food_items = food_items
        self._owned = owned
        self._food_stock = food_stock
        self._parent_view = parent_view
        self._selected_item = None

        if not food_items:
            options = [discord.SelectOption(label="No food available", value="__none__")]
            disabled = True
        else:
            options = []
            for item in food_items:
                count = owned.get(item.name, 0)
                units = (item.parameters or {}).get("food_units", 0)
                options.append(
                    discord.SelectOption(
                        label=f"{item.name} ({units} units each, {count} owned)",
                        value=item.name,
                    )
                )
            disabled = False

        select = Select(placeholder="Choose food to deposit", options=options[:25], disabled=disabled)
        select.callback = self._on_select
        self.add_item(select)
        self._select = select

        self._feed_btn = Button(label="Feed ×1", style=discord.ButtonStyle.success, disabled=True, row=1)
        self._feed_btn.callback = self._on_feed
        self.add_item(self._feed_btn)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🍖 Feed Kennel",
            description=f"Current food stock: **{self._food_stock}** units.\nSelect food items to deposit.",
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self._select.values[0]
        if value == "__none__":
            return
        self._selected_item = next((i for i in self._food_items if i.name == value), None)
        self._feed_btn.disabled = self._selected_item is None or self._owned.get(value, 0) <= 0
        for opt in self._select.options:
            opt.default = opt.value == value
        await r.edit(view=self)

    async def _on_feed(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        if self._selected_item is None:
            return
        ok, message, new_stock = await feed_kennel(self._owner_id, self._kennel_id, self._selected_item.name)
        if not ok:
            await re.reply(content=message)
            return
        self._food_stock = new_stock
        if isinstance(self._parent_view, PaginatorView):
            await self._parent_view.refresh(interaction)
        await re.reply(content=f"✅ {message}")
