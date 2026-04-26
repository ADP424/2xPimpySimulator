from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.ui.util import edit_interaction, reply_to_interacted_message

if TYPE_CHECKING:
    from src.game.models import Disease


def build_disease_info_embed(disease: Disease) -> discord.Embed:
    """Build an info embed for a disease.

    Parameters
    ----------
    disease: Disease
        The disease to display.

    Returns
    -------
    discord.Embed
        The formatted embed.
    """

    embed = discord.Embed(title=disease.name, description=disease.description or "No description.")
    embed.add_field(
        name="Health Impact",
        value=disease.health_impact.replace("_", " ").capitalize(),
        inline=True,
    )
    embed.add_field(name="Category", value=disease.category or "—", inline=True)
    embed.add_field(
        name="Contagious",
        value=f"{round(disease.contagion_chance * 100)}%" if disease.contagion_chance > 0 else "No",
        inline=True,
    )
    if disease.sexually_transmitted:
        embed.add_field(name="Transmission", value="Sexually transmitted", inline=True)
    if disease.recovery_chance > 0:
        embed.add_field(name="Recovery Chance", value=f"{round(disease.recovery_chance * 100)}%/day", inline=True)
    else:
        embed.add_field(
            name="Recovery Chance", value="Requires treatment" if disease.treatable else "None", inline=True
        )
    embed.add_field(name="Treatable", value="Yes" if disease.treatable else "No", inline=True)
    embed.add_field(name="Curable", value="Yes" if disease.curable else "No (permanent)", inline=True)
    if disease.heritability > 0:
        embed.add_field(name="Heritability", value=f"{round(disease.heritability * 100)}%", inline=True)
    if disease.seasons:
        embed.add_field(name="Seasons", value=", ".join(s.capitalize() for s in disease.seasons), inline=True)
    if disease.immunity_duration:
        embed.add_field(name="Immunity After Recovery", value=f"{disease.immunity_duration} days", inline=True)
    return embed


@dataclass
class DiseaseOption:
    disease: Disease
    label: str


class DiseaseDropdownControls:
    """Reusable dropdown + info button for showing general disease info."""

    def __init__(self, diseases: list[DiseaseOption], placeholder: str = "Select a disease"):
        self.diseases = diseases
        self.selected: Optional[Disease] = None

        if not diseases:
            options = [discord.SelectOption(label="No diseases", value="__none__")]
        else:
            options = [discord.SelectOption(label=o.label, value=str(o.disease.id)) for o in diseases]

        self.select = Select(
            placeholder=placeholder,
            options=options,
            disabled=not bool(diseases),
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info

        if not diseases:
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
        selected = next((o.disease for o in self.diseases if o.disease.id == selected_id), None)
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
        embed = build_disease_info_embed(self.selected)
        await reply_to_interacted_message(interaction, embed=embed)
