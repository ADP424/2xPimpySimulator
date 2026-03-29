import os
from typing import TYPE_CHECKING, Optional, Sequence

import discord
from discord.ui import Select, View

from src.bot.constants import BREEDING_COOLDOWN_HEATING_UP_THRESHOLD, VIEW_TIMEOUT
from src.bot.ui.util import (
    InteractionResponder,
    mention,
)
from src.game import get_pooch_family
from src.game.models import Mutation, PoochBreedInfo

from .components import build_breed_info_embed, build_mutation_info_embed

if TYPE_CHECKING:
    from src.game.models import Owner, Pooch, Server


class _FamilySelect(Select):
    def __init__(self, members: Sequence["Pooch"], placeholder: str, kind: str, empty_label: str):
        # Always render a dropdown (Discord UI row budget is fixed at 0..4).
        # If there are no members, show a disabled dropdown with a single "None" option.
        if not members:
            options = [discord.SelectOption(label=empty_label, value="__none__")]
        else:
            options = [discord.SelectOption(label=member.name, value=str(member.id)) for member in members]

        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=not bool(members),
            min_values=1,
            max_values=1,
        )
        self.kind = kind
        self._members = list(members)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.values[0]
        for opt in self.options:
            opt.default = opt.value == value

        await r.edit(view=self.view)

        if value == "__none__":
            return

        selected_id = int(value)
        selected_member = next((m for m in self._members if m.id == selected_id), None)
        if selected_member is None:
            return

        view = self.view
        if not isinstance(view, PoochInfoView):
            return

        next_view = PoochInfoView(server=view.server, pooch=selected_member, owner=view.owner)
        embed = await next_view.build_embed()
        await r.reply(embed=embed, view=next_view)


class _BreedSelect(Select):
    def __init__(self, pooch_breeds: Sequence[PoochBreedInfo], placeholder: str, empty_label: str):
        if not pooch_breeds:
            options = [discord.SelectOption(label=empty_label, value="__none__")]
        else:
            options = [
                discord.SelectOption(
                    label=f"{pooch_breed.breed.name} ({round(100 * pooch_breed.relative_weight)}%)",
                    value=str(pooch_breed.breed.id),
                )
                for pooch_breed in pooch_breeds
            ]

        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=not bool(pooch_breeds),
            min_values=1,
            max_values=1,
        )
        self._pooch_breeds = list(pooch_breeds)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.values[0]
        for option in self.options:
            option.default = option.value == value

        await r.edit(view=self.view)

        if value == "__none__":
            return

        breed_id = int(value)
        selected = next(
            (pooch_breed.breed for pooch_breed in self._pooch_breeds if pooch_breed.breed.id == breed_id), None
        )
        if selected is None:
            return

        embed = build_breed_info_embed(selected)
        await r.reply(embed=embed)


class _MutationSelect(Select):
    def __init__(self, mutations: Sequence[Mutation], placeholder: str, empty_label: str):
        if not mutations:
            options = [discord.SelectOption(label=empty_label, value="__none__")]
        else:
            options = [discord.SelectOption(label=mutation.name, value=str(mutation.id)) for mutation in mutations]

        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=(not bool(mutations)),
            min_values=1,
            max_values=1,
        )
        self._mutations = list(mutations)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.values[0]
        for option in self.options:
            option.default = option.value == value

        await r.edit(view=self.view)

        if value == "__none__":
            return

        mutation_id = int(value)
        selected = next((mutation for mutation in self._mutations if mutation.id == mutation_id), None)
        if selected is None:
            return

        embed = build_mutation_info_embed(selected)
        await r.reply(embed=embed)


class PoochInfoView(View):
    def __init__(self, *, server: Server, pooch: Pooch, owner: Optional[Owner], timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server = server
        self.pooch = pooch
        self.owner = owner

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner is None:
            return True
        return interaction.user.id == self.owner.discord_id

    @staticmethod
    def _format_breeding_status(cooldown: int) -> str:
        if cooldown == 0:
            return "In Heat"
        if cooldown <= BREEDING_COOLDOWN_HEATING_UP_THRESHOLD:
            return "Heating Up"
        return "Cooled"

    @staticmethod
    def _format_size(size: int) -> str:
        return str(size)

    async def build_embed(self) -> discord.Embed:
        self.clear_items()

        family = await get_pooch_family(self.pooch.id)
        is_dev = os.getenv("STAGE", "dev").lower() == "dev"

        embed = discord.Embed(title=self.pooch.name)
        embed.add_field(name="Age", value=str(self.pooch.age), inline=True)
        embed.add_field(name="Sex", value=self.pooch.sex.capitalize(), inline=True)
        embed.add_field(name="Size", value=self._format_size(self.pooch.size), inline=True)

        embed.add_field(
            name="Owner",
            value=(
                mention(self.pooch.owner_discord_id)
                if self.pooch.owner_discord_id
                else (self.pooch.vendor.name if self.pooch.vendor is not None else "Nobody")
            ),
            inline=True,
        )
        embed.add_field(name="Health Status", value=self.pooch.status.capitalize(), inline=True)
        embed.add_field(name="Birthday", value=str(self.pooch.birthday.date()), inline=True)

        embed.add_field(
            name="Breeding Status", value=self._format_breeding_status(self.pooch.breeding_cooldown), inline=True
        )
        embed.add_field(name="Sexual Status", value=("Virgin" if self.pooch.virgin else "Debauched"), inline=True)

        mood_emojis = {
            "happy": "😊",
            "excited": "🤪",
            "sleepy": "😴",
            "grumpy": "😤",
            "anxious": "😰",
            "mischievous": "😈",
            "zoomies": "🏃",
            "hungry": "🍖",
            "content": "😌",
            "clingy": "🥺",
            "dead": "💀",
        }
        if self.pooch.mood:
            mood_label = f"{mood_emojis.get(self.pooch.mood, '')} {self.pooch.mood.capitalize()}"
        else:
            mood_label = "—"
        embed.add_field(name="Mood", value=mood_label, inline=True)

        parents = family.get("parents", [])
        children = family.get("children", [])
        siblings = family.get("siblings", [])

        embed.add_field(name="Parents", value=", ".join(parent.name for parent in parents) or "Unknown", inline=False)
        embed.add_field(name="Children", value=", ".join(child.name for child in children) or "None", inline=False)
        embed.add_field(name="Siblings", value=", ".join(sibling.name for sibling in siblings) or "None", inline=False)

        if self.pooch.breeds:
            breed_text = ", ".join(
                f"{pooch_breed.breed.name} ({round(100 * pooch_breed.relative_weight)}%)"
                for pooch_breed in self.pooch.breeds
            )
        else:
            breed_text = "None"

        if self.pooch.mutations:
            mutation_text = ", ".join(mutation.name for mutation in self.pooch.mutations) or "None"
        else:
            mutation_text = "None"

        embed.add_field(name="Breeds", value=breed_text, inline=False)
        embed.add_field(name="Mutations", value=mutation_text, inline=False)

        if is_dev:
            p = self.pooch
            if p.breeds:
                total_weight = sum(pb.relative_weight for pb in p.breeds)
                avg_min = round(sum(pb.breed.min_size * pb.relative_weight for pb in p.breeds) / total_weight)
                avg_max = round(sum(pb.breed.max_size * pb.relative_weight for pb in p.breeds) / total_weight)
                size_bounds = f"{avg_min}–{avg_max}"
            else:
                size_bounds = "N/A"
            dev_lines = [
                f"Health: {p.health} (base {p.base_health}, age loss {p.health_loss_age})",
                f"Breeding Cooldown: {p.breeding_cooldown}",
                f"Size Bounds: {size_bounds}",
                f"Strength: {p.strength}",
                f"Cuteness: {p.cuteness}",
                f"Fluffiness: {p.fluffiness}",
                f"Intelligence: {p.intelligence}",
                f"Dexterity: {p.dexterity}",
                f"Fertility: {p.fertility}",
                f"Aggressiveness: {p.aggressiveness}",
            ]
            embed.add_field(name="[DEV] Stats", value="\n".join(dev_lines), inline=False)

        row = 0
        if parents:
            parent_select = _FamilySelect(parents, placeholder="Parents", kind="parents", empty_label="Unknown parents")
            parent_select.row = row
            row += 1
            self.add_item(parent_select)

        if children:
            child_select = _FamilySelect(children, placeholder="Children", kind="children", empty_label="No children")
            child_select.row = row
            row += 1
            self.add_item(child_select)

        if siblings:
            sibling_select = _FamilySelect(siblings, placeholder="Siblings", kind="siblings", empty_label="No siblings")
            sibling_select.row = row
            row += 1
            self.add_item(sibling_select)

        if self.pooch.breeds:
            breed_select = _BreedSelect(self.pooch.breeds, placeholder="Breeds", empty_label="No breeds")
            breed_select.row = row
            row += 1
            self.add_item(breed_select)

        if self.pooch.mutations:
            mutation_select = _MutationSelect(self.pooch.mutations, placeholder="Mutations", empty_label="No mutations")
            mutation_select.row = row
            self.add_item(mutation_select)

        return embed
