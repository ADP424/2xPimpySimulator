import discord
from discord.ui import Button, Select, View
from typing import TYPE_CHECKING, List, Optional, Tuple

from .pooch_info import PoochInfoView
from .components.paginator import PageSource, PaginatorView
from bot.ui.util import edit_interaction

if TYPE_CHECKING:
    from game.model import Server, Pooch


class DayChangeStatusPageSource(PageSource):
    def __init__(self, *, server: Server, pooches: List[Pooch], title: str, description: str):
        self.server = server
        self.pooches = pooches
        self.title = title
        self.description = description

    async def load(self):
        return

    def page_count(self) -> int:
        return max((len(self.pooches) + 9) // 10, 1)

    async def render(self, view: View, page_index: int) -> Tuple[Optional[str], Optional[discord.Embed]]:
        start = page_index * 10
        end = min(start + 10, len(self.pooches))
        pooches = self.pooches[start:end]

        embed = discord.Embed(title=self.title, description=self.description)

        embed.add_field(
            name=f"Mentioned Pooches ({start + 1}-{end} of {len(self.pooches)})",
            value="\n".join(f"• {pooch.name}" for pooch in pooches) or "None",
            inline=False,
        )

        controls = _StatusControls(server=self.server, pooches=pooches)
        controls.attach(view)
        return None, embed


class _StatusControls:
    def __init__(self, *, server: Server, pooches: list[Pooch]):
        self.server = server
        self.pooches = pooches
        self.selected_pooch: Optional[Pooch] = None

        self.select = Select(
            placeholder="Select a pooch to view info",
            options=(
                [discord.SelectOption(label=pooch.name, value=str(pooch.id)) for pooch in pooches] if pooches else []
            ),
            disabled=not bool(pooches),
        )
        self.select.callback = self._on_select  # type: ignore

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info  # type: ignore

    def attach(self, view: View):
        view.add_item(self.select)
        view.add_item(self.info_button)

    async def _on_select(self, interaction: discord.Interaction):
        selected_id = int(self.select.values[0])
        self.selected_pooch = next((pooch for pooch in self.pooches if pooch.id == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False
        await edit_interaction(interaction, view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected_pooch is None:
            return
        info_view = PoochInfoView(server=self.server, pooch=self.selected_pooch, owner=None)
        embed = await info_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=info_view)


class PublicPaginatorView(PaginatorView):
    def __init__(self, source: PageSource):
        super().__init__(source, owner_discord_id=0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True


def make_status_view(*, server: Server, pooches: List[Pooch], title: str, description: str) -> PublicPaginatorView:
    source = DayChangeStatusPageSource(server=server, pooches=pooches, title=title, description=description)
    return PublicPaginatorView(source)
