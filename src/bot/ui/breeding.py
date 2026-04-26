from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ui import Select, View

from src.bot.ui.util import InteractionResponder
from src.game import breed_pooches

if TYPE_CHECKING:
    from src.game.models import Pooch


class BreedMateView(View):
    def __init__(self, pooch: Pooch, mates: list[Pooch]):
        super().__init__(timeout=120)
        self.pooch = pooch
        self.mates = mates

        options = [discord.SelectOption(label=mate.name, value=str(mate.id)) for mate in mates]
        self.select = Select(
            placeholder=f"Choose a mate for {pooch.name}.",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        mate_id = int(self.select.values[0])
        mate = next((mate for mate in self.mates if mate.id == mate_id), None)
        if mate is None:
            return

        self.select.disabled = True
        await r.edit(view=self)

        try:
            breeding_result = await breed_pooches(self.pooch.id, mate.id, return_disease_events=True)
        except TypeError:
            breeding_result = await breed_pooches(self.pooch.id, mate.id)
        except ValueError as exception:
            await r.reply(content=str(exception))
            return

        if isinstance(breeding_result, tuple) and len(breeding_result) == 2:
            puppies, disease_events = breeding_result
        else:
            puppies = breeding_result
            disease_events = []

        if len(puppies) == 1:
            message = f"✅ **Breeding successful.** {self.pooch.name} and {mate.name} are expecting **1** puppy."
        elif len(puppies) == 2:
            message = f"✅ **Twins!** {self.pooch.name} and {mate.name} are expecting **2** puppies."
        else:
            message = f"✅ **Triplets!** {self.pooch.name} and {mate.name} are expecting **3** puppies."

        if disease_events:
            event_lines = []
            for pooch_id, public_label, event_type in disease_events:
                name = self.pooch.name if pooch_id == self.pooch.id else mate.name if pooch_id == mate.id else "A puppy"
                if event_type == "spread":
                    event_lines.append(f"• {name} was exposed to {public_label}.")
                elif event_type == "inherited":
                    event_lines.append(f"• A puppy inherited {public_label}.")
            if event_lines:
                message += "\n" + "\n".join(event_lines)

        await r.reply(content=message)
