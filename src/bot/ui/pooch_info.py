from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, Sequence

import discord
from discord.ui import Button, Select, View

from src.bot.constants import VIEW_TIMEOUT
from src.bot.ui.util import (
    InteractionResponder,
    mention,
)
from src.game import (
    SNAPSHOT_BIRTH,
    SNAPSHOT_BREEDING,
    SNAPSHOT_DEATH,
    SNAPSHOT_LITTER,
    SNAPSHOT_MEDICAL_EXAM,
    SNAPSHOT_OWNERSHIP,
    SNAPSHOT_VET_DISEASES,
    SNAPSHOT_VET_INJURIES,
    SNAPSHOT_VET_MUTATIONS,
    get_effective_stat,
    get_pooch_family,
    get_pooch_timeline,
)
from src.game.models import (
    Mutation,
    PoochBreedInfo,
    PoochTimelineEntry,
    get_breeding_status,
)
from src.game.utils.obfuscation import health_label, starvation_label

from .components import (
    PageSource,
    PaginatorView,
    build_breed_info_embed,
    build_disease_info_embed,
    build_injury_info_embed,
    build_mutation_info_embed,
)

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


class _InjurySelect(Select):
    def __init__(self, injuries: Sequence, placeholder: str, empty_label: str):
        if not injuries:
            options = [discord.SelectOption(label=empty_label, value="__none__")]
        else:
            options = [discord.SelectOption(label=injury.name, value=str(injury.id)) for injury in injuries]

        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=(not bool(injuries)),
            min_values=1,
            max_values=1,
        )
        self._injuries = list(injuries)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.values[0]
        for option in self.options:
            option.default = option.value == value

        await r.edit(view=self.view)

        if value == "__none__":
            return

        injury_id = int(value)
        selected = next((injury for injury in self._injuries if injury.id == injury_id), None)
        if selected is None:
            return

        embed = build_injury_info_embed(selected)
        await r.reply(embed=embed)


class _DiseaseSelect(Select):
    def __init__(self, diseases: Sequence, placeholder: str, empty_label: str):
        if not diseases:
            options = [discord.SelectOption(label=empty_label, value="__none__")]
        else:
            options = [discord.SelectOption(label=disease.name, value=str(disease.id)) for disease in diseases]

        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=(not bool(diseases)),
            min_values=1,
            max_values=1,
        )
        self._diseases = list(diseases)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.values[0]
        for option in self.options:
            option.default = option.value == value

        await r.edit(view=self.view)

        if value == "__none__":
            return

        disease_id = int(value)
        selected = next((disease for disease in self._diseases if disease.id == disease_id), None)
        if selected is None:
            return

        embed = build_disease_info_embed(selected)
        await r.reply(embed=embed)


_BREEDING_STATUS_LABELS = {
    "in_heat": "In Heat",
    "heating_up": "Heating Up",
    "cooled": "Cooled",
}


class PoochInfoView(View):
    def __init__(
        self, *, server: Optional[Server], pooch: Pooch, owner: Optional[Owner], timeout: float = VIEW_TIMEOUT
    ):
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
        return _BREEDING_STATUS_LABELS[get_breeding_status(cooldown)]

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
        size = await get_effective_stat(self.pooch.id, "size")
        embed.add_field(
            name="Size", value=self._format_size(size if size is not None else self.pooch.size), inline=True
        )

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
        if self.pooch.alive:
            embed.add_field(name="Health", value=health_label(self.pooch.health), inline=True)
        embed.add_field(name="Birthday", value=str(self.pooch.birthday.date()), inline=True)

        embed.add_field(
            name="Breeding Status", value=self._format_breeding_status(self.pooch.breeding_cooldown), inline=True
        )
        embed.add_field(name="Sexual Status", value=("Virgin" if self.pooch.virgin else "Debauched"), inline=True)

        # Pregnancy
        if getattr(self.pooch, "pregnancy_timer", None) is not None:
            embed.add_field(name="Pregnant", value="🤰 Expecting!", inline=True)

        # Immortality
        if getattr(self.pooch, "immortal", False):
            embed.add_field(name="Immortal", value="☠️ Undying", inline=True)

        # Rejuvenation count
        try:
            rejuv_count = int(getattr(self.pooch, "rejuvenation_count", 0) or 0)
        except TypeError, ValueError:
            rejuv_count = 0
        if rejuv_count > 0:
            embed.add_field(name="Rejuvenations", value=str(rejuv_count), inline=True)

        # Starvation
        try:
            starvation = int(getattr(self.pooch, "starvation", 0) or 0)
        except TypeError, ValueError:
            starvation = 0
        if starvation > 0:
            embed.add_field(name="Hunger", value=starvation_label(starvation), inline=True)

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

        mutation_display_parts = []
        for pm in self.pooch.mutations:
            if pm.visible:
                mutation_display_parts.append(pm.mutation.name)
            elif pm.displayed_symptom:
                mutation_display_parts.append(pm.displayed_symptom)
        mutation_text = ", ".join(mutation_display_parts) or "None"

        injury_display_parts = []
        for pi in self.pooch.injuries:
            if pi.visible:
                injury_display_parts.append(pi.injury.name)
            elif pi.displayed_symptom:
                injury_display_parts.append(pi.displayed_symptom)
        injury_text = ", ".join(injury_display_parts) or "None"

        disease_display_parts = []
        for pd in self.pooch.diseases:
            if pd.visible:
                disease_display_parts.append(pd.disease.name)
            elif pd.displayed_symptom:
                disease_display_parts.append(pd.displayed_symptom)
        disease_text = ", ".join(disease_display_parts) or "None"

        embed.add_field(name="Breeds", value=breed_text, inline=False)
        embed.add_field(name="Mutations", value=mutation_text, inline=False)
        embed.add_field(name="Injuries", value=injury_text, inline=False)
        embed.add_field(name="Diseases", value=disease_text, inline=False)

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
                f"Size: {p.size} (bounds: {size_bounds})",
                f"Strength: {p.strength}",
                f"Cuteness: {p.cuteness}",
                f"Fluffiness: {p.fluffiness}",
                f"Intelligence: {p.intelligence}",
                f"Dexterity: {p.dexterity}",
                f"Fertility: {p.fertility}",
                f"Aggressiveness: {p.aggressiveness}",
            ]
            embed.add_field(name="[DEV] Stats", value="\n".join(dev_lines), inline=False)

        # Rows 0–3 for selects, row 4 reserved for the timeline button
        row = 0
        if parents and row < 4:
            parent_select = _FamilySelect(parents, placeholder="Parents", kind="parents", empty_label="Unknown parents")
            parent_select.row = row
            row += 1
            self.add_item(parent_select)

        if children and row < 4:
            child_select = _FamilySelect(children, placeholder="Children", kind="children", empty_label="No children")
            child_select.row = row
            row += 1
            self.add_item(child_select)

        if siblings and row < 4:
            sibling_select = _FamilySelect(siblings, placeholder="Siblings", kind="siblings", empty_label="No siblings")
            sibling_select.row = row
            row += 1
            self.add_item(sibling_select)

        if self.pooch.breeds and row < 4:
            breed_select = _BreedSelect(self.pooch.breeds, placeholder="Breeds", empty_label="No breeds")
            breed_select.row = row
            row += 1
            self.add_item(breed_select)

        visible_mutations = [pm.mutation for pm in self.pooch.mutations if pm.visible]
        if visible_mutations and row < 4:
            mutation_select = _MutationSelect(visible_mutations, placeholder="Mutations", empty_label="No mutations")
            mutation_select.row = row
            row += 1
            self.add_item(mutation_select)

        visible_injuries = [pi.injury for pi in self.pooch.injuries if pi.visible]
        if visible_injuries and row < 4:
            injury_select = _InjurySelect(visible_injuries, placeholder="Injuries", empty_label="No injuries")
            injury_select.row = row
            row += 1
            self.add_item(injury_select)

        visible_diseases = [pd.disease for pd in self.pooch.diseases if pd.visible]
        if visible_diseases and row < 4:
            disease_select = _DiseaseSelect(visible_diseases, placeholder="Diseases", empty_label="No diseases")
            disease_select.row = row
            self.add_item(disease_select)

        timeline_btn = Button(label="Timeline", style=discord.ButtonStyle.secondary, row=4)
        timeline_btn.callback = self._on_timeline
        self.add_item(timeline_btn)

        return embed

    async def _on_timeline(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        entries = await get_pooch_timeline(self.pooch.id)
        if not entries:
            re = InteractionResponder(interaction, ephemeral=True)
            await re.reply(content=f"No timeline entries found for {self.pooch.name}.")
            return
        source = _TimelinePageSource(pooch=self.pooch, entries=entries)
        view = PaginatorView(source, owner_discord_id=interaction.user.id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


_SNAPSHOT_KIND_LABEL = {
    SNAPSHOT_BIRTH: "Birth",
    SNAPSHOT_DEATH: "Death",
    SNAPSHOT_OWNERSHIP: "Ownership Change",
    SNAPSHOT_BREEDING: "Breeding",
    SNAPSHOT_LITTER: "Litter",
    SNAPSHOT_VET_INJURIES: "Vet Visit — Injuries",
    SNAPSHOT_VET_MUTATIONS: "Vet Visit — Mutations",
    SNAPSHOT_VET_DISEASES: "Vet Visit — Diseases",
    SNAPSHOT_MEDICAL_EXAM: "Medical Exam",
}


class _TimelinePageSource(PageSource):
    """One timeline entry per page, oldest to newest."""

    def __init__(self, pooch, entries: list[PoochTimelineEntry]):
        self._pooch = pooch
        self._entries = entries

    async def load(self):
        pass  # entries already loaded

    def page_count(self) -> int:
        return max(len(self._entries), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        entry = self._entries[page_index]
        total = len(self._entries)
        kind_label = _SNAPSHOT_KIND_LABEL.get(entry.kind, entry.kind.replace("_", " ").title())

        timestamp = entry.snapshot_at.strftime("%Y-%m-%d %H:%M UTC")
        embed = discord.Embed(
            title=f"{self._pooch.name}'s Timeline ({page_index + 1}/{total})",
            description=f"**{kind_label}**\n{entry.description}\n\n*{timestamp}*",
        )

        if entry.entity_names is not None:
            label = {
                SNAPSHOT_VET_INJURIES: "Injuries on record",
                SNAPSHOT_VET_DISEASES: "Diseases on record",
            }.get(entry.kind, "Mutations on record")
            names = ", ".join(entry.entity_names) if entry.entity_names else "None"
            embed.add_field(name=label, value=names, inline=False)

        return None, embed
