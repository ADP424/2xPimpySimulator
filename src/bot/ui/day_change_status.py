from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from bot.constants import ITEMS_PER_PAGE
from bot.ui.util import defer_interaction, edit_interaction, reply_to_interacted_message

from .components.paginator import PageSource, PaginatorView
from .pooch_info import PoochInfoView

if TYPE_CHECKING:
    from game.models import BirthEvent, DeathEvent, OtherEvent, Pooch, Server


class DayChangeStatusPageSource(PageSource):
    def __init__(
        self,
        server: Server,
        births: list[BirthEvent],
        deaths: list[DeathEvent],
        other_events: list[OtherEvent],
        title: str,
        description: str,
    ):
        self.server = server
        self.births = births
        self.deaths = deaths
        self.other_events = other_events
        self.title = title
        self.description = description

    async def load(self):
        return

    def page_count(self) -> int:
        birth_pages = (len(self.births) + (ITEMS_PER_PAGE - 1)) // ITEMS_PER_PAGE
        death_pages = (len(self.deaths) + (ITEMS_PER_PAGE - 1)) // ITEMS_PER_PAGE
        other_event_pages = (len(self.other_events) + (ITEMS_PER_PAGE - 1)) // ITEMS_PER_PAGE
        return max(birth_pages, death_pages, other_event_pages, 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        birth_start = page_index * ITEMS_PER_PAGE
        birth_end = min(birth_start + ITEMS_PER_PAGE, len(self.births))
        death_start = page_index * ITEMS_PER_PAGE
        death_end = min(death_start + ITEMS_PER_PAGE, len(self.deaths))
        other_event_start = page_index * ITEMS_PER_PAGE
        other_event_end = min(other_event_start + ITEMS_PER_PAGE, len(self.other_events))

        births = self.births[birth_start:birth_end]
        deaths = self.deaths[death_start:death_end]
        other_events = self.other_events[other_event_start:other_event_end]

        def _dedupe_pooches(pooches: list[Pooch]) -> list[Pooch]:
            return list({pooch.id: pooch for pooch in pooches}.values())

        birthed_pooches = _dedupe_pooches([birth.child for birth in births])
        dead_pooches = _dedupe_pooches([death.pooch for death in deaths])
        other_pooches = _dedupe_pooches([other_event.pooch for other_event in other_events])

        embed = discord.Embed(title=self.title, description=self.description)

        embed.add_field(
            name=f"Births ({birth_start + 1}-{birth_end} of {len(self.births)})" if self.births else "Births",
            value="\n".join(f"• {birth.message}" for birth in births) or "None",
            inline=False,
        )
        embed.add_field(
            name=f"Deaths ({death_start + 1}-{death_end} of {len(self.deaths)})" if self.deaths else "Deaths",
            value="\n".join(f"• {death.message}" for death in deaths) or "None",
            inline=False,
        )
        embed.add_field(
            name=(
                f"Miscellaneous ({other_event_start + 1}-{other_event_end} of {len(self.other_events)})"
                if self.other_events
                else "Miscellaneous Events"
            ),
            value="\n".join(f"• {other_event.message}" for other_event in other_events) or "None",
            inline=False,
        )

        controls = _StatusControls(
            server=self.server, birthed_pooches=birthed_pooches, dead_pooches=dead_pooches, other_pooches=other_pooches
        )
        controls.attach(view)
        return None, embed


class _StatusControls:
    def __init__(
        self, server: Server, birthed_pooches: list[Pooch], dead_pooches: list[Pooch], other_pooches: list[Pooch]
    ):
        self.server = server
        self.birthed_pooches = birthed_pooches
        self.dead_pooches = dead_pooches
        self.other_pooches = other_pooches
        self.selected_pooch: Optional[Pooch] = None

        self.selected_born_id: Optional[int] = None
        self.selected_dead_id: Optional[int] = None
        self.selected_other_id: Optional[int] = None

        self.born_select = Select(
            placeholder="Newly born pooches",
            options=(
                [discord.SelectOption(label=pooch.name, value=str(pooch.id)) for pooch in birthed_pooches]
                if birthed_pooches
                else [discord.SelectOption(label="No pooches were born today", value="__none__")]
            ),
            disabled=not bool(birthed_pooches),
        )
        self.born_select.callback = self._on_born_select  # type: ignore

        self.dead_select = Select(
            placeholder="Newly dead pooches",
            options=(
                [discord.SelectOption(label=pooch.name, value=str(pooch.id)) for pooch in dead_pooches]
                if dead_pooches
                else [discord.SelectOption(label="No pooches died today", value="__none__")]
            ),
            disabled=not bool(dead_pooches),
        )
        self.dead_select.callback = self._on_dead_select  # type: ignore

        self.other_select = Select(
            placeholder="Miscellaneous pooches",
            options=(
                [discord.SelectOption(label=pooch.name, value=str(pooch.id)) for pooch in other_pooches]
                if other_pooches
                else [discord.SelectOption(label="No miscellaneous events today", value="__none__")]
            ),
            disabled=not bool(other_pooches),
        )
        self.other_select.callback = self._on_other_select  # type: ignore

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info  # type: ignore

    def attach(self, view: View):
        self.born_select.row = 1
        self.dead_select.row = 2
        self.other_select.row = 3
        self.info_button.row = 4
        view.add_item(self.born_select)
        view.add_item(self.dead_select)
        view.add_item(self.other_select)
        view.add_item(self.info_button)

    async def _on_born_select(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        selected_id = int(self.born_select.values[0])
        self.selected_born_id = selected_id
        self.selected_dead_id = None
        self.selected_other_id = None

        self.selected_pooch = next((pooch for pooch in self.birthed_pooches if pooch.id == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False

        # Persist selection
        for option in self.born_select.options:
            option.default = option.value == str(selected_id)
        for option in self.dead_select.options:
            option.default = False
        for option in self.other_select.options:
            option.default = False

        await edit_interaction(interaction, view=self.born_select.view)

    async def _on_dead_select(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        selected_id = int(self.dead_select.values[0])
        self.selected_dead_id = selected_id
        self.selected_born_id = None
        self.selected_other_id = None

        self.selected_pooch = next((pooch for pooch in self.dead_pooches if pooch.id == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False

        # Persist selection
        for option in self.dead_select.options:
            option.default = option.value == str(selected_id)
        for option in self.born_select.options:
            option.default = False
        for option in self.other_select.options:
            option.default = False

        await edit_interaction(interaction, view=self.dead_select.view)

    async def _on_other_select(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        selected_id = int(self.other_select.values[0])
        self.selected_other_id = selected_id
        self.selected_born_id = None
        self.selected_dead_id = None

        self.selected_pooch = next((pooch for pooch in self.other_pooches if pooch.id == selected_id), None)
        if self.selected_pooch is None:
            return
        self.info_button.disabled = False

        # Persist selection
        for option in self.other_select.options:
            option.default = option.value == str(selected_id)
        for option in self.born_select.options:
            option.default = False
        for option in self.dead_select.options:
            option.default = False

        await edit_interaction(interaction, view=self.other_select.view)

    async def _on_info(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        if self.selected_pooch is None:
            return
        info_view = PoochInfoView(server=self.server, pooch=self.selected_pooch, owner=None)
        embed = await info_view.build_embed()
        await reply_to_interacted_message(interaction, embed=embed, view=info_view)


class PublicPaginatorView(PaginatorView):
    def __init__(self, source: PageSource):
        super().__init__(source, owner_discord_id=0)

    async def interaction_check(self, _: discord.Interaction) -> bool:
        return True


def make_status_view(
    server: Server,
    births: list[BirthEvent],
    deaths: list[DeathEvent],
    other_events: list[OtherEvent],
    title: str,
    description: str,
) -> PublicPaginatorView:
    source = DayChangeStatusPageSource(
        server=server, births=births, deaths=deaths, other_events=other_events, title=title, description=description
    )
    return PublicPaginatorView(source)
