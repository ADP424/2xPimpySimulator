from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.ui.util import edit_interaction, reply_to_interacted_message

if TYPE_CHECKING:
    from src.database.models import Injury


def build_injury_info_embed(injury: Injury) -> discord.Embed:
    """
    Build injury info embed.

    Parameters
    ----------
    injury: Any
        The `injury` value.

    Returns
    -------
    Any
        The result of calling `build_injury_info_embed`.
    """

    embed = discord.Embed(title=injury.name, description=injury.description or "No description.")
    embed.add_field(
        name="Health Impact",
        value=injury.health_impact.replace("_", " ").capitalize(),
        inline=True,
    )
    embed.add_field(
        name="Severity",
        value=injury.severity.capitalize(),
        inline=True,
    )
    params = injury.parameters or {}
    if params.get("persistence"):
        embed.add_field(name="Persistence", value=str(params["persistence"]), inline=True)
    if injury.treated:
        treated_impact = injury.treated.get("health_impact")
        treated_desc = injury.treated.get("description") or "Treatable"
        treated_value = treated_desc
        if treated_impact:
            treated_value += f" ({treated_impact.replace('_', ' ').capitalize()})"
        embed.add_field(name="Treated", value=treated_value, inline=False)
    return embed


@dataclass
class InjuryOption:
    injury: Injury
    label: str


class InjuryDropdownControls:
    """Reusable dropdown + info button for showing general injury info."""

    def __init__(self, injuries: list[InjuryOption], placeholder: str = "Select an injury"):
        # Injuries don't have a rarity enum; they have a severity enum. Sort
        # "most common" first, which for severity means trivial injuries first.
        _SEVERITY_ORDER = {
            "trivial": 0,
            "minor": 1,
            "moderate": 2,
            "major": 3,
            "critical": 4,
            "remarkable": 5,
            "catastrophic": 6,
        }
        injuries = sorted(
            injuries,
            key=lambda o: (
                _SEVERITY_ORDER.get(str(getattr(o.injury, "severity", "moderate")).lower(), 99),
                getattr(o.injury, "name", "") or "",
            ),
        )
        self.injuries = injuries
        self.selected: Optional[Injury] = None

        if not injuries:
            options = [discord.SelectOption(label="No injuries", value="__none__")]
        else:
            options = [discord.SelectOption(label=o.label, value=str(o.injury.id)) for o in injuries]

        self.select = Select(
            placeholder=placeholder,
            options=options,
            disabled=not bool(injuries),
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info

        if not injuries:
            self.info_button.disabled = True

    def attach(self, view: View, row: int):
        self.select.row = row
        self.info_button.row = row + 1
        view.add_item(self.select)
        view.add_item(self.info_button)

    async def _on_select(self, interaction: discord.Interaction):
        value = self.select.values[0]
        if value == "__none__":
            self.selected = None
            self.info_button.disabled = True
            for opt in self.select.options:
                opt.default = False
            await edit_interaction(interaction, view=self.select.view)
            return

        selected_id = int(value)
        selected = next((o.injury for o in self.injuries if o.injury.id == selected_id), None)
        if selected is None:
            return
        self.selected = selected
        self.info_button.disabled = False

        for opt in self.select.options:
            opt.default = opt.value == value

        await edit_interaction(interaction, view=self.select.view)

    async def _on_info(self, interaction: discord.Interaction):
        if self.selected is None:
            return
        embed = build_injury_info_embed(self.selected)
        await reply_to_interacted_message(interaction, embed=embed)
