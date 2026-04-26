from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.ui.util import edit_interaction, reply_to_interacted_message

if TYPE_CHECKING:
    from src.game.models import Breed


def build_breed_info_embed(breed: Breed) -> discord.Embed:
    """
    Build breed info embed.

    Parameters
    ----------
    breed: Any
        The `breed` value.

    Returns
    -------
    Any
        The result of calling `build_breed_info_embed`.
    """

    embed = discord.Embed(title=breed.name, description=breed.description)
    embed.add_field(name="Also Known As", value=breed.alt_name or "—", inline=True)
    embed.add_field(name="Category", value=breed.category or "—", inline=True)
    embed.add_field(name="Rarity", value=breed.rarity.capitalize(), inline=True)
    return embed


@dataclass
class BreedOption:
    breed: Breed
    label: str


class BreedDropdownControls:
    """Reusable dropdown + info button for showing general breed info."""

    def __init__(self, breeds: list[BreedOption], placeholder: str = "Select a breed"):
        self.breeds = breeds
        self.selected: Optional[Breed] = None

        if not breeds:
            options = [discord.SelectOption(label="No breeds", value="__none__")]
        else:
            options = [discord.SelectOption(label=o.label, value=str(o.breed.id)) for o in breeds]

        self.select = Select(
            placeholder=placeholder,
            options=options,
            disabled=not bool(breeds),
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info

        if not breeds:
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
        selected = next((o.breed for o in self.breeds if o.breed.id == selected_id), None)
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
        embed = build_breed_info_embed(self.selected)
        await reply_to_interacted_message(interaction, embed=embed)
