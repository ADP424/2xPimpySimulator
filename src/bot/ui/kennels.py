from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.constants import MAX_NAME_LENGTH
from src.bot.ui.util import InteractionResponder
from src.game import (
    get_or_create_owner,
    get_or_create_server,
    list_kennel_pooches,
    list_owner_kennels,
    rename_kennel,
    rename_pooch,
)

if TYPE_CHECKING:
    from src.game.models import Kennel, Pooch

from .breeding import BreedMateView
from .components import PageSource
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
        self.rename_kennel_button.callback = self._on_rename_kennel

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.breed_button = Button(label="Breed", style=discord.ButtonStyle.secondary, disabled=True)
        self.walk_button = Button(label="Walk", style=discord.ButtonStyle.secondary, disabled=True)
        self.rename_pooch_button = Button(label="Rename Pooch", style=discord.ButtonStyle.secondary, disabled=True)

        self.info_button.callback = self._on_info
        self.breed_button.callback = self._on_breed
        self.walk_button.callback = self._noop
        self.rename_pooch_button.callback = self._on_rename_pooch

        if not pooches:
            self.info_button.disabled = True
            self.breed_button.disabled = True
            self.walk_button.disabled = True
            self.rename_pooch_button.disabled = True

    def attach(self, view: View):
        self.rename_kennel_button.row = 0
        self.select.row = 1
        self.info_button.row = 2
        self.breed_button.row = 2
        self.walk_button.row = 2
        self.rename_pooch_button.row = 2

        view.add_item(self.rename_kennel_button)
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.breed_button)
        view.add_item(self.walk_button)
        view.add_item(self.rename_pooch_button)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        selected_id = self.select.values[0]
        self.selected_pooch = next((pooch for pooch in self.pooches if pooch.id == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False
        self.breed_button.disabled = False
        self.walk_button.disabled = False
        self.rename_pooch_button.disabled = False

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

        view = BreedMateView(pooch=pooch, mates=mates)
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
        from .components import PaginatorView

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
        ok = await rename_pooch(self._pooch_id)
        if not ok:
            await r.reply(content=f"That name is too long. Keep it under {MAX_NAME_LENGTH} characters.")
            return

        from .components import PaginatorView

        if isinstance(self._parent_view, PaginatorView):
            await self._parent_view.refresh(interaction)

        await r.reply(content=f"✅ Renamed pooch to **{new_name}**")
