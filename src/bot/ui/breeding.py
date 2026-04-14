from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ui import Select, View

from src.bot.ui.util import InteractionResponder
from src.game import breed_pooches
from src.game.breeding import compute_breeding_chance, select_actual_mate

if TYPE_CHECKING:
    from src.game.models import Pooch


class BreedMateView(View):
    def __init__(self, pooch: Pooch, mates: list[Pooch]):
        super().__init__(timeout=120)
        self.pooch = pooch
        self.mates = mates

        chance_pct = round(compute_breeding_chance(getattr(pooch, "intelligence", 10)) * 100)
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
        import random

        r = InteractionResponder(interaction)
        mate_id = int(self.select.values[0])
        intended_mate = next((m for m in self.mates if m.id == mate_id), None)
        if intended_mate is None:
            return

        self.select.disabled = True
        await r.edit(view=self)

        # Intelligence-based mate selection (Section 7A)
        rng = random.Random()
        if self.pooch.sex == "male":
            male, eligible_females = self.pooch, self.mates
        else:
            male = intended_mate
            eligible_females = [m for m in self.mates if m.sex != self.pooch.sex]

        actual_mate = await select_actual_mate(male, intended_mate, eligible_females, rng=rng)
        distracted = actual_mate.id != intended_mate.id

        try:
            breeding_result = await breed_pooches(self.pooch.id, actual_mate.id, return_disease_events=True)
        except TypeError:
            breeding_result = await breed_pooches(self.pooch.id, actual_mate.id)
        except ValueError as exception:
            await r.reply(content=str(exception))
            return

        if isinstance(breeding_result, tuple) and len(breeding_result) == 2:
            puppies, disease_events = breeding_result
        else:
            puppies = breeding_result
            disease_events = []

        if distracted:
            prefix = (
                f"💫 **{self.pooch.name} got distracted** and ended up mating with **{actual_mate.name}** instead!\n"
            )
        else:
            prefix = ""

        if len(puppies) == 1:
            message = (
                f"{prefix}✅ **Breeding successful.** {self.pooch.name} and {actual_mate.name} "
                f"are expecting **1** puppy."
            )
        elif len(puppies) == 2:
            message = f"{prefix}✅ **Twins!** {self.pooch.name} and {actual_mate.name} are expecting **2** puppies."
        else:
            message = f"{prefix}✅ **Triplets!** {self.pooch.name} and {actual_mate.name} are expecting **3** puppies."

        if disease_events:
            event_lines = []
            for pooch_id, public_label, event_type in disease_events:
                name = (
                    self.pooch.name
                    if pooch_id == self.pooch.id
                    else actual_mate.name if pooch_id == actual_mate.id else "A puppy"
                )
                if event_type == "spread":
                    event_lines.append(f"• {name} was exposed to {public_label}.")
                elif event_type == "inherited":
                    event_lines.append(f"• A puppy inherited {public_label}.")
            if event_lines:
                message += "\n" + "\n".join(event_lines)

        await r.reply(content=message)
