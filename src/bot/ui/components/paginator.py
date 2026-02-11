import discord
from discord.ui import View, Button
from typing import Optional, Protocol

from bot.ui.util import edit_interaction


class PageSource(Protocol):
    async def load(self): ...
    def page_count(self) -> int: ...
    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]: ...


class PaginatorView(View):

    def __init__(self, source: PageSource, owner_id: int, *, timeout: float = 300):
        super().__init__(timeout=timeout)
        self._source = source
        self._owner_id = owner_id
        self._page = 0

        self._prev = Button(label="◀", style=discord.ButtonStyle.secondary, disabled=True)
        self._next = Button(label="▶", style=discord.ButtonStyle.secondary, disabled=True)
        self._prev.callback = self._on_prev  # type: ignore
        self._next.callback = self._on_next  # type: ignore

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

    def _clamp_page(self):
        max_page = max(self._source.page_count() - 1, 0)
        self._page = max(0, min(self._page, max_page))

    def _update_nav_disabled(self):
        count = self._source.page_count()
        self._prev.disabled = (count <= 1) or (self._page <= 0)
        self._next.disabled = (count <= 1) or (self._page >= count - 1)

    async def _render(self, interaction: discord.Interaction):
        self._clamp_page()
        self.clear_items()
        self.add_item(self._prev)
        self.add_item(self._next)
        self._update_nav_disabled()
        content, embed = await self._source.render(self, self._page)
        await edit_interaction(interaction, content=content, embed=embed, view=self)

    async def _on_prev(self, interaction: discord.Interaction):
        self._page -= 1
        await self._render(interaction)

    async def _on_next(self, interaction: discord.Interaction):
        self._page += 1
        await self._render(interaction)
