from __future__ import annotations

from typing import Optional, Protocol

import discord
from discord.ui import Button, View

from src.bot.constants import VIEW_TIMEOUT
from src.bot.ui.util import edit_interaction


class PageSource(Protocol):
    async def load(self): ...
    def page_count(self) -> int: ...
    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]: ...


class PaginatorView(View):

    def __init__(self, source: PageSource, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._source = source
        self._owner_id = owner_discord_id
        self._page = 0

        self._prev = Button(label="◀", style=discord.ButtonStyle.secondary, disabled=True, row=0)
        self._next = Button(label="▶", style=discord.ButtonStyle.secondary, disabled=True, row=0)
        self._prev.callback = self._on_prev
        self._next.callback = self._on_next

        self.add_item(self._prev)
        self.add_item(self._next)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def start(self, interaction: discord.Interaction):
        await self._source.load()
        self._page = 0
        await self._render(interaction)

    async def refresh(self, interaction: discord.Interaction):
        await self._source.load()
        await self._render(interaction)

    async def build_first_page(self) -> tuple[Optional[str], Optional[discord.Embed]]:
        """
        Prepare and return the first page content/embed without editing a message.
        """

        await self._source.load()
        self._page = 0
        return await self._build_page()

    def _clamp_page(self):
        max_page = max(self._source.page_count() - 1, 0)
        self._page = max(0, min(self._page, max_page))

    def _update_nav_disabled(self):
        count = self._source.page_count()
        self._prev.disabled = (count <= 1) or (self._page <= 0)
        self._next.disabled = (count <= 1) or (self._page >= count - 1)

    async def _build_page(self) -> tuple[Optional[str], Optional[discord.Embed]]:
        self._clamp_page()
        self.clear_items()
        self.add_item(self._prev)
        self.add_item(self._next)
        self._update_nav_disabled()
        return await self._source.render(self, self._page)

    async def _render(self, interaction: discord.Interaction):
        content, embed = await self._build_page()
        await edit_interaction(interaction, content=content, embed=embed, view=self)

    async def _on_prev(self, interaction: discord.Interaction):
        self._page -= 1
        await self._render(interaction)

    async def _on_next(self, interaction: discord.Interaction):
        self._page += 1
        await self._render(interaction)
