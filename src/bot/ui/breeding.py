from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ui import Select, View

from src.bot.ui.util import InteractionResponder
from src.game import (
    breed_with_mate_choice,
    describe_breeding_outcome,
)

if TYPE_CHECKING:
    from src.game.models import Pooch


class BreedMateView(View):
    def __init__(self, pooch: Pooch, mates: list[Pooch], chance: float):
        super().__init__(timeout=120)
        self.pooch = pooch
        self.mates = mates

        chance_pct = round(chance * 100)
        options = [discord.SelectOption(label=mate.name, value=str(mate.id)) for mate in mates]
        self.select = Select(
            placeholder=f"Choose a mate for {pooch.name} ({chance_pct}% chance).",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        mate_id = int(self.select.values[0])
        if not any(m.id == mate_id for m in self.mates):
            return

        self.select.disabled = True
        await r.edit(view=self)

        try:
            outcome = await breed_with_mate_choice(interaction.user.id, self.pooch.id, mate_id)
        except ValueError as exception:
            await r.reply(content=str(exception))
            return

        message, disease_lines = describe_breeding_outcome(outcome)
        message = f"{'💫 ' if outcome.distracted else ''}✅ {message}"
        if disease_lines:
            message += "\n" + "\n".join(f"• {line}" for line in disease_lines)
        await r.reply(content=message)
