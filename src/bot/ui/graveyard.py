from __future__ import annotations

from math import ceil
from typing import Optional

import discord
from discord.ui import Select, View

from src.game import get_or_create_server, list_graveyard_pooches

from .components import PageSource
from .pooch_info import PoochInfoView
from .util import InteractionResponder

PAGE_SIZE = 10


class GraveyardPageSource(PageSource):
    """Paginated list of a player's deceased pooches."""

    def __init__(self, server_discord_id: int, owner_discord_id: int):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._rows: list[tuple] = []

    async def load(self):
        # rows are (Pooch, buried_at)
        self._rows = await list_graveyard_pooches(self.owner_discord_id)

    def page_count(self) -> int:
        return max(ceil(len(self._rows) / PAGE_SIZE), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._rows:
            embed = discord.Embed(
                title="Your Graveyard",
                description="No headstones yet. (Dead pooches you own will appear here.)",
            )
            return "**Your Graveyard**", embed

        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        page_rows = self._rows[start:end]

        total_pages = self.page_count()
        embed = discord.Embed(title=f"Graveyard ({page_index + 1}/{total_pages})")
        lines: list[str] = []
        for i, (pooch, buried_at) in enumerate(page_rows):
            when = buried_at.date().isoformat() if buried_at is not None else "????-??-??"
            lines.append(f"{start + i + 1}. ⚰️ **{pooch.name}** — buried {when}")
        embed.description = "\n".join(lines)

        controls = _GraveyardControls(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            page_rows=page_rows,
        )
        controls.attach(view)

        return "**Your Graveyard**", embed


class _GraveyardControls:
    def __init__(self, server_discord_id: int, owner_discord_id: int, page_rows: list[tuple]):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.page_rows = page_rows

        options = [discord.SelectOption(label=pooch.name, value=str(pooch.id)) for (pooch, _) in page_rows]
        self.select = Select(
            placeholder="Inspect a headstone",
            options=options or [discord.SelectOption(label="No pooches", value="__none__")],
            disabled=not bool(options),
        )
        self.select.callback = self._on_select

    def attach(self, view: View):
        self.select.row = 1
        view.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.select.values[0]
        for option in self.select.options:
            option.default = option.value == value
        await r.edit(view=self.select.view)

        if value == "__none__":
            return

        selected_id = int(value)
        selected = next((pooch for (pooch, _) in self.page_rows if pooch.id == selected_id), None)
        if selected is None:
            return

        server = await get_or_create_server(self.server_discord_id)
        view = PoochInfoView(server=server, pooch=selected, owner=None)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)
