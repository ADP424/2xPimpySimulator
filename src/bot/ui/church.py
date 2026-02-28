from __future__ import annotations

from typing import Optional

import discord
from discord.ui import Button, Select, View

from bot.constants import VIEW_TIMEOUT
from bot.ui.util import InteractionResponder
from game import (
    get_or_create_server,
    get_pooch_bloodskull_value,
    get_summon_pooch_price,
    list_hell_pooches,
    list_kennel_pooches,
    list_owner_kennels,
    sacrifice_pooch,
    summon_pooch,
)
from game.models import Kennel, Pooch
from logger import get_logger

from .components.paginator import PageSource, PaginatorView
from .pooch_info import PoochInfoView

logger = get_logger("bot/ui/church")


class ChurchView(View):
    """Town Church. The spooky stuff lives in the basement."""

    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

        self.add_item(_BasementButton(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))
        self.add_item(_TownButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id


class _TownButton(Button):
    def __init__(self):
        super().__init__(label="Town", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        from .town import TownView  # local import to dodge circular dependencies

        await r.reply(content="**Welcome to the Town**", view=TownView())


class _BasementButton(Button):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(label="Basement", style=discord.ButtonStyle.danger, row=0)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        view = BasementView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
        await r.reply(content=_basement_banner(), view=view)


def _basement_banner() -> str:
    return (
        "⛧⛧⛧ **THE BASEMENT** ⛧⛧⛧\n"
        "The air is cold. Candles gutter. A chalk circle pulses with pentagrams.\n"
        "𖤐 𖤐 𖤐\n"
    )


class BasementView(View):
    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

        self.add_item(_SacrificeButton(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))
        self.add_item(_SummonButton(owner_discord_id=owner_discord_id))
        self.add_item(_HellButton(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))
        self.add_item(_BackToChurchButton(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id


class _BackToChurchButton(Button):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(label="Upstairs", style=discord.ButtonStyle.secondary, row=2)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        await r.reply(
            content="**Welcome to the Church**",
            view=ChurchView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id),
        )


class _SacrificeButton(Button):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(label="Sacrifice a Pooch", style=discord.ButtonStyle.danger, row=0)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = _SacrificeKennelsPageSource(
            server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id
        )
        view = PaginatorView(source, owner_discord_id=self.owner_discord_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class _SummonButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="Summon a Pooch", style=discord.ButtonStyle.danger, row=0)
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        view = _SummonView(owner_discord_id=self.owner_discord_id)
        await r.reply(content="Choose your ritual strength:", view=view)


class _HellButton(Button):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(label="Gaze Into Hell", style=discord.ButtonStyle.secondary, row=1)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = _HellPageSource(server_discord_id=self.server_discord_id)
        view = PaginatorView(source, owner_discord_id=self.owner_discord_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


# -----------------------------
# Summoning
# -----------------------------


class _SummonView(View):
    def __init__(self, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id
        # Provide a few common presets, plus a custom option.
        self.add_item(_SummonRollButton(owner_discord_id, rolls=1))
        self.add_item(_SummonRollButton(owner_discord_id, rolls=5))
        self.add_item(_SummonRollButton(owner_discord_id, rolls=10))
        self.add_item(_CustomSummonButton(owner_discord_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id


class _SummonRollButton(Button):
    def __init__(self, owner_discord_id: int, rolls: int):
        price = get_summon_pooch_price(rolls)
        super().__init__(
            label=f"Summon ({rolls} roll{'s' if rolls != 1 else ''}) — {price} 𖤐",
            style=discord.ButtonStyle.danger,
        )
        self._owner_id = owner_discord_id
        self._rolls = rolls

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        await r.defer(thinking=True)
        try:
            success, message = await summon_pooch(self._owner_id, num_rolls=self._rolls)
        except Exception as exception:
            logger.error(f"Error during pooch summon: '{exception}'")
            await r.finish_with_error("The ritual fizzled unexpectedly.")
            return

        if not success:
            await r.reply(content=message)
            return

        await r.reply(content=f"✅ {message}")


class _CustomSummonButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="Custom…", style=discord.ButtonStyle.secondary, row=1)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        # Modals can only be shown via the raw interaction response.
        if interaction.user.id != self._owner_id:
            return
        await interaction.response.send_modal(_CustomSummonModal(owner_discord_id=self._owner_id))


class _CustomSummonModal(discord.ui.Modal):
    def __init__(self, owner_discord_id: int):
        super().__init__(title="Custom Summon")
        self._owner_id = owner_discord_id
        self.rolls = discord.ui.TextInput(
            label="Number of rolls",
            placeholder="e.g. 7",
            min_length=1,
            max_length=4,
            required=True,
        )
        self.add_item(self.rolls)

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)

        if interaction.user.id != self._owner_id:
            await r.reply(content="That's not your ritual circle.")
            return

        try:
            num_rolls = int(str(self.rolls.value).strip())
        except Exception:
            await r.reply(content="Enter a whole number of rolls (like 7).")
            return

        if num_rolls < 1:
            await r.reply(content="You need to make at least 1 roll.")
            return
        if num_rolls > 9999:
            await r.reply(content="That many rolls would tear the veil. Pick a smaller number.")
            return

        price = get_summon_pooch_price(num_rolls)
        view = _ConfirmSummonView(owner_discord_id=self._owner_id, num_rolls=num_rolls, price=price)
        await r.reply(
            content=(
                f"You scratch **{num_rolls}** marks into the chalk circle.\n"
                f"This ritual will cost **{price}** 𖤐 bloodskulls.\n\nProceed?"
            ),
            view=view,
        )


class _ConfirmSummonView(View):
    def __init__(self, owner_discord_id: int, num_rolls: int, price: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id
        self._num_rolls = num_rolls
        self._price = price

        self.add_item(_ConfirmSummonButton(owner_discord_id, num_rolls=num_rolls, price=price))
        self.add_item(_CancelSummonButton(owner_discord_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id


class _ConfirmSummonButton(Button):
    def __init__(self, owner_discord_id: int, num_rolls: int, price: int):
        super().__init__(label=f"Confirm — {price} 𖤐", style=discord.ButtonStyle.danger)
        self._owner_id = owner_discord_id
        self._num_rolls = num_rolls

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        await r.defer(thinking=True)
        try:
            success, message = await summon_pooch(self._owner_id, num_rolls=self._num_rolls)
        except Exception as exception:
            logger.error(f"Error during pooch summon: '{exception}'")
            await r.finish_with_error("The ritual fizzled unexpectedly.")
            return

        if not success:
            await r.reply(content=message)
            return

        await r.reply(content=f"✅ {message}")


class _CancelSummonButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="Cancel", style=discord.ButtonStyle.secondary)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        # Return to the standard summon preset view.
        await r.edit(content="Choose your ritual strength:", view=_SummonView(owner_discord_id=self._owner_id))


# -----------------------------
# Hell viewing
# -----------------------------


class _HellPageSource(PageSource):
    def __init__(self, server_discord_id: int):
        self.server_discord_id = server_discord_id
        self._pooches: list[Pooch] = []

    async def load(self):
        self._pooches = await list_hell_pooches()

    def page_count(self) -> int:
        return max(len(self._pooches), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._pooches:
            return "⛧ Hell is quiet... for now.", discord.Embed(
                title="Hell", description="No pooches have been damned."
            )

        pooch = self._pooches[page_index]
        value = await get_pooch_bloodskull_value(pooch.id)

        embed = discord.Embed(
            title=f"⛧ {pooch.name} ⛧",
            description=(
                "A name scratched into obsidian. A faint whine echoes through the brimstone.\n"
                f"𖤐 Bloodskull value: **{value}**\n"
                "✶ ✶ ✶"
            ),
        )

        controls = _HellControls(server_discord_id=self.server_discord_id, pooch=pooch)
        controls.attach(view)
        return "**Hell**", embed


class _HellControls:
    def __init__(self, server_discord_id: int, pooch: Pooch):
        self.server_discord_id = server_discord_id
        self.pooch = pooch
        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, row=1)
        self.info_button.callback = self._on_info  # type: ignore

    def attach(self, view: View):
        view.add_item(self.info_button)

    async def _on_info(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        server = await get_or_create_server(self.server_discord_id)
        view = PoochInfoView(server=server, pooch=self.pooch, owner=None)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)


# -----------------------------
# Sacrifice flow (kennel picker)
# -----------------------------


class _SacrificeKennelsPageSource(PageSource):
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
            return (
                _basement_banner(),
                discord.Embed(title="Sacrifice", description="You don't have any kennels... so nothing to offer."),
            )

        kennel = self._kennels[page_index]
        pooches = await list_kennel_pooches(kennel.id)

        embed = discord.Embed(
            title=f"⛧ Offering Bowl — {kennel.name}",
            description=(
                f"Choose a living pooch to place within the circle.\n"
                f"{len(pooches)} / {kennel.pooch_limit} in this kennel\n"
                "𖤐 𖤐 𖤐"
            ),
        )

        values: dict[int, int] = {}
        for pooch in pooches:
            if pooch.alive:
                values[pooch.id] = await get_pooch_bloodskull_value(pooch.id)

        controls = _SacrificeControls(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            pooches=[p for p in pooches if p.alive],
            values_by_pooch_id=values,
        )
        controls.attach(view)
        return _basement_banner(), embed


class _SacrificeControls:
    def __init__(
        self,
        server_discord_id: int,
        owner_discord_id: int,
        pooches: list[Pooch],
        values_by_pooch_id: dict[int, int],
    ):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.pooches = pooches
        self.values_by_pooch_id = values_by_pooch_id
        self.selected: Optional[Pooch] = None

        if not pooches:
            options = [discord.SelectOption(label="No living pooches here", value="__none__")]
        else:
            options = [
                discord.SelectOption(
                    label=f"{p.name} (𖤐 {values_by_pooch_id.get(p.id, 0)})",
                    value=str(p.id),
                )
                for p in pooches
            ]

        self.select = Select(placeholder="Select an offering", options=options, disabled=not bool(pooches))
        self.select.callback = self._on_select  # type: ignore

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.sacrifice_button = Button(label="SACRIFICE", style=discord.ButtonStyle.danger, disabled=True)

        self.info_button.callback = self._on_info  # type: ignore
        self.sacrifice_button.callback = self._on_sacrifice  # type: ignore

    def attach(self, view: View):
        self.select.row = 1
        self.info_button.row = 2
        self.sacrifice_button.row = 2
        view.add_item(self.select)
        view.add_item(self.info_button)
        view.add_item(self.sacrifice_button)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.select.values[0]
        if value == "__none__":
            self.selected = None
            self.info_button.disabled = True
            self.sacrifice_button.disabled = True
            for option in self.select.options:
                option.default = False
        else:
            selected_id = int(value)
            self.selected = next((p for p in self.pooches if p.id == selected_id), None)
            if self.selected is None:
                return
            self.info_button.disabled = False
            self.sacrifice_button.disabled = False
            for option in self.select.options:
                option.default = option.value == value

        await r.edit(view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected is None:
            return
        server = await get_or_create_server(self.server_discord_id)
        view = PoochInfoView(server=server, pooch=self.selected, owner=None)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_sacrifice(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected is None:
            return
        await r.defer(thinking=True)

        try:
            success, message = await sacrifice_pooch(self.owner_discord_id, self.selected.id)
        except Exception as exception:
            logger.error(f"Error during pooch sacrifice: '{exception}'")
            await r.finish_with_error("The circle cracked. Something went wrong.")
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
