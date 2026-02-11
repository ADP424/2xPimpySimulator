import discord
from discord.ui import View, Select, Button
from typing import List, Optional, Tuple

from game import get_pooch_by_id
from .pooch_info import PoochInfoView
from .components.paginator import PageSource, PaginatorView
from bot.ui.util import edit_interaction


class DayChangeStatusPageSource(PageSource):
    def __init__(self, *, server_id: int, pooch_ids: List[int], title: str, description: str):
        self.server_id = server_id
        self.pooch_ids = pooch_ids
        self.title = title
        self.description = description

    async def load(self):
        return

    def page_count(self) -> int:
        return max((len(self.pooch_ids) + 9) // 10, 1)

    async def render(self, view: View, page_index: int) -> Tuple[Optional[str], Optional[discord.Embed]]:
        start = page_index * 10
        end = min(start + 10, len(self.pooch_ids))
        page_ids = self.pooch_ids[start:end]

        embed = discord.Embed(title=self.title, description=self.description)

        pooches = []
        for pid in page_ids:
            try:
                pooches.append(await get_pooch_by_id(self.server_id, pid))
            except Exception:
                continue

        embed.add_field(
            name=f"Mentioned Pooches ({start+1}-{end} of {len(self.pooch_ids)})",
            value="\n".join(f"• {p.name} (ID {p.id})" for p in pooches) or "None",
            inline=False,
        )

        controls = _StatusControls(server_id=self.server_id, pooches=pooches)
        controls.attach(view)
        return None, embed


class _StatusControls:
    def __init__(self, *, server_id: int, pooches: list):
        self.server_id = server_id
        self.pooches = pooches
        self.selected_pooch_id: Optional[int] = None

        self.select = Select(
            placeholder="Select a pooch to view info",
            options=[discord.SelectOption(label=p.name, value=str(p.id)) for p in pooches] if pooches else [],
            disabled=not bool(pooches),
        )
        self.select.callback = self._on_select  # type: ignore

        self.info_btn = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_btn.callback = self._on_info  # type: ignore

    def attach(self, view: View):
        view.add_item(self.select)
        view.add_item(self.info_btn)

    async def _on_select(self, interaction: discord.Interaction):
        self.selected_pooch_id = int(self.select.values[0])
        self.info_btn.disabled = False
        await edit_interaction(interaction, view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected_pooch_id is None:
            return
        info_view = PoochInfoView(server_id=self.server_id, pooch_id=self.selected_pooch_id, owner_id=None)
        embed = await info_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=info_view)


class PublicPaginatorView(PaginatorView):
    def __init__(self, source: PageSource):
        super().__init__(source, owner_id=0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True


def make_status_view(*, server_id: int, pooch_ids: List[int], title: str, description: str) -> PublicPaginatorView:
    source = DayChangeStatusPageSource(server_id=server_id, pooch_ids=pooch_ids, title=title, description=description)
    return PublicPaginatorView(source)
