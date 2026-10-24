from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.ui.util import edit_interaction, format_stat_effects, reply_to_interacted_message

if TYPE_CHECKING:
    from src.game.models import Mutation


def build_mutation_info_embed(mutation: Mutation) -> discord.Embed:
    """
    Build mutation info embed.

    Parameters
    ----------
    mutation: Any
        The `mutation` value.

    Returns
    -------
    Any
        The result of calling `build_mutation_info_embed`.
    """

    embed = discord.Embed(title=mutation.name, description=mutation.description)
    embed.add_field(name="Also Known As", value=mutation.alt_name or "—", inline=True)
    embed.add_field(name="Category", value=mutation.category or "—", inline=True)
    embed.add_field(name="Rarity", value=mutation.rarity.capitalize(), inline=True)
    embed.add_field(name="Health Impact", value=mutation.health_impact.replace("_", " ").capitalize(), inline=True)
    embed.add_field(name="Heritability", value=f"{round(mutation.heritability * 100)}%", inline=True)
    embed.add_field(
        name="Affects",
        value=(
            ", ".join(
                [
                    "Females" if mutation.affects_females else "",
                    "Males" if mutation.affects_males else "",
                ]
            )
            .replace(", ,", ",")
            .strip(", ")
            or "None"
        ),
        inline=True,
    )
    embed.add_field(name="Stat Effects", value=format_stat_effects(mutation.parameters), inline=False)
    return embed


@dataclass
class MutationOption:
    mutation: Mutation
    label: str


class MutationDropdownControls:
    """Reusable dropdown + info button for showing general mutation info."""

    def __init__(self, mutations: list[MutationOption], placeholder: str = "Select a mutation"):
        from src.game.utils.rarity_sort import sort_by_rarity_weight

        mutations = sort_by_rarity_weight(
            mutations,
            key=lambda o: getattr(o.mutation, "rarity", None),
            secondary=lambda o: getattr(o.mutation, "name", "") or "",
        )
        self.mutations = mutations
        self.selected: Optional[Mutation] = None

        if not mutations:
            options = [discord.SelectOption(label="No mutations", value="__none__")]
        else:
            options = [discord.SelectOption(label=o.label, value=str(o.mutation.id)) for o in mutations]

        self.select = Select(
            placeholder=placeholder,
            options=options,
            disabled=not bool(mutations),
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select

        self.info_button = Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info

        if not mutations:
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
        selected = next((o.mutation for o in self.mutations if o.mutation.id == selected_id), None)
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
        embed = build_mutation_info_embed(self.selected)
        await reply_to_interacted_message(interaction, embed=embed)
