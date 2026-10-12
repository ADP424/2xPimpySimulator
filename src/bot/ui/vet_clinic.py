from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.constants import (
    DISCORD_DESCRIPTION_MAX_LENGTH,
    DISCORD_LABEL_MAX_LENGTH,
    DISCORD_SELECT_MAX_OPTIONS,
    VIEW_TIMEOUT,
)
from src.bot.ui.util import InteractionResponder
from src.game import (
    MEDICAL_EXAM_COST,
    diagnose_diseases,
    diagnose_injuries,
    diagnose_mutations,
    get_diagnose_diseases_cost,
    get_diagnose_injuries_cost,
    get_diagnose_mutations_cost,
    get_disease_treatment_cost,
    get_pooch_disease_instances,
    get_pooch_injury_instances,
    get_public_injury_label,
    get_treatment_cost,
    is_injury_treated_today,
    list_all_breeds,
    list_all_diseases,
    list_all_injuries,
    list_all_mutations,
    list_kennel_pooches,
    list_owner_kennels,
    medical_exam,
    treat_disease,
    treat_injury,
)

if TYPE_CHECKING:
    from src.database.models import Injury
    from src.game.models import Breed, Disease, Mutation, Pooch

from src.game.manage_diseases import get_public_disease_label

from .components import (
    BreedDropdownControls,
    BreedOption,
    DiseaseDropdownControls,
    DiseaseOption,
    InjuryDropdownControls,
    InjuryOption,
    MutationDropdownControls,
    MutationOption,
    PageSource,
    PaginatorView,
)

PAGE_SIZE = 10


class VetClinicView(View):
    def __init__(self, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id

        self.add_item(_ListBreedsButton(owner_discord_id=owner_discord_id))
        self.add_item(_ListMutationsButton(owner_discord_id=owner_discord_id))
        self.add_item(_ListInjuriesButton(owner_discord_id=owner_discord_id))
        self.add_item(_ListDiseasesButton(owner_discord_id=owner_discord_id))
        self.add_item(_PatientRoomButton(owner_discord_id=owner_discord_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id


class _ListBreedsButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="List Breeds", style=discord.ButtonStyle.primary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = BreedListPageSource()
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class _ListMutationsButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="List Mutations", style=discord.ButtonStyle.primary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = MutationListPageSource()
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class BreedListPageSource(PageSource):
    def __init__(self):
        self._breeds: list[Breed] = []

    async def load(self):
        self._breeds = await list_all_breeds()

    def page_count(self) -> int:
        return max(ceil(len(self._breeds) / PAGE_SIZE), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._breeds:
            return "Breeds:", discord.Embed(title="Breeds", description="No breeds found.")

        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = self._breeds[start:end]

        total_pages = self.page_count()
        embed = discord.Embed(title=f"Breeds ({page_index + 1}/{total_pages})")
        embed.description = "\n".join(f"{start + i + 1}. {b.name}" for i, b in enumerate(page_items))

        controls = BreedDropdownControls(
            breeds=[BreedOption(breed=b, label=b.name) for b in page_items],
            placeholder="Select a breed (this page)",
        )
        controls.attach(view, row=1)

        return "Breeds:", embed


class _ListInjuriesButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="List Injuries", style=discord.ButtonStyle.primary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = InjuryListPageSource()
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class MutationListPageSource(PageSource):
    def __init__(self):
        self._mutations: list[Mutation] = []

    async def load(self):
        self._mutations = await list_all_mutations()

    def page_count(self) -> int:
        return max(ceil(len(self._mutations) / PAGE_SIZE), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._mutations:
            return "Mutations:", discord.Embed(title="Mutations", description="No mutations found.")

        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = self._mutations[start:end]

        total_pages = self.page_count()
        embed = discord.Embed(title=f"Mutations ({page_index + 1}/{total_pages})")
        embed.description = "\n".join(f"{start + i + 1}. {m.name}" for i, m in enumerate(page_items))

        controls = MutationDropdownControls(
            mutations=[MutationOption(mutation=m, label=m.name) for m in page_items],
            placeholder="Select a mutation (this page)",
        )
        controls.attach(view, row=1)

        return "Mutations:", embed


class _PatientRoomButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="Patient Room", style=discord.ButtonStyle.secondary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        kennels = await list_owner_kennels(self._owner_id)
        kennel_pooches: list[tuple] = []
        for kennel in kennels:
            pooches = await list_kennel_pooches(kennel.id)
            if pooches:
                kennel_pooches.append((kennel, pooches))

        if not kennel_pooches:
            re = InteractionResponder(interaction, ephemeral=True)
            await re.reply(content="You have no pooches right now.")
            return

        source = _PatientRoomPageSource(owner_discord_id=self._owner_id, kennel_pooches=kennel_pooches)
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class _PatientRoomPageSource(PageSource):
    """One page per kennel; each page shows a dropdown of that kennel's pooches."""

    def __init__(self, owner_discord_id: int, kennel_pooches: list[tuple]):
        self._owner_id = owner_discord_id
        self._kennel_pooches = kennel_pooches  # list of (Kennel, list[Pooch])

    async def load(self):
        pass  # data already loaded by the button callback

    def page_count(self) -> int:
        return max(len(self._kennel_pooches), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        kennel, pooches = self._kennel_pooches[page_index]
        total_pages = self.page_count()

        embed = discord.Embed(
            title=f"Patient Room — {kennel.name} ({page_index + 1}/{total_pages})",
            description="Select a pooch to treat or diagnose.",
        )

        def _label(p: Pooch) -> str:
            suffix = " (checked)" if p.vet_checked else ""
            return (p.name + suffix)[:DISCORD_LABEL_MAX_LENGTH]

        def _desc(p: Pooch) -> str:
            parts = []
            if p.injuries:
                parts.append(f"{len(p.injuries)} injur{'y' if len(p.injuries) == 1 else 'ies'}")
            hidden_mut = sum(1 for pm in p.mutations if not pm.visible)
            if hidden_mut:
                parts.append(f"{hidden_mut} hidden mutation{'s' if hidden_mut != 1 else ''}")
            return ", ".join(parts)[:DISCORD_DESCRIPTION_MAX_LENGTH]

        options = [
            discord.SelectOption(
                label=_label(p),
                value=str(p.id),
                description=_desc(p) or None,
            )
            for p in pooches[:DISCORD_SELECT_MAX_OPTIONS]
        ]

        select = Select(placeholder="Select a pooch", options=options, min_values=1, max_values=1)

        async def _on_select(interaction: discord.Interaction):
            r = InteractionResponder(interaction)
            pooch_id = int(select.values[0])
            pooch = next((p for p in pooches if p.id == pooch_id), None)
            if pooch is None:
                await r.finish_with_error("Pooch not found.")
                return
            patient_view = _PatientRoomView(owner_discord_id=self._owner_id, pooch=pooch)
            patient_embed = await patient_view.build_embed()
            await r.reply(embed=patient_embed, view=patient_view)

        select.callback = _on_select
        select.row = 2
        view.add_item(select)

        return None, embed


class _PatientRoomView(View):
    """Shows treat / diagnose-injuries / diagnose-mutations buttons for a specific pooch."""

    def __init__(self, owner_discord_id: int, pooch: Pooch, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id
        self._pooch = pooch

        injure_cost = get_diagnose_injuries_cost()
        mutate_cost = get_diagnose_mutations_cost()
        disease_cost = get_diagnose_diseases_cost()

        treat_btn = Button(label="Treat Injury", style=discord.ButtonStyle.primary, row=0)
        treat_btn.callback = self._on_treat
        self.add_item(treat_btn)

        treat_disease_btn = Button(label="Treat Disease", style=discord.ButtonStyle.primary, row=0)
        treat_disease_btn.callback = self._on_treat_disease
        self.add_item(treat_disease_btn)

        diag_inj_btn = Button(label=f"Diagnose Injuries (${injure_cost})", style=discord.ButtonStyle.secondary, row=1)
        diag_inj_btn.callback = self._on_diagnose_injuries
        self.add_item(diag_inj_btn)

        diag_mut_btn = Button(label=f"Diagnose Mutations (${mutate_cost})", style=discord.ButtonStyle.secondary, row=1)
        diag_mut_btn.callback = self._on_diagnose_mutations
        self.add_item(diag_mut_btn)

        diag_dis_btn = Button(label=f"Diagnose Diseases (${disease_cost})", style=discord.ButtonStyle.secondary, row=1)
        diag_dis_btn.callback = self._on_diagnose_diseases
        self.add_item(diag_dis_btn)

        exam_btn = Button(label=f"Medical Exam (${MEDICAL_EXAM_COST})", style=discord.ButtonStyle.secondary, row=2)
        exam_btn.callback = self._on_medical_exam
        self.add_item(exam_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def build_embed(self) -> discord.Embed:
        p = self._pooch
        inj_count = len(p.injuries)
        disease_count = len(p.diseases)
        hidden_mut = sum(1 for pm in p.mutations if not pm.visible)
        hidden_dis = sum(1 for pd in p.diseases if not pd.visible)
        lines = []
        if inj_count:
            lines.append(f"**Injuries:** {inj_count}")
        if disease_count:
            lines.append(f"**Diseases:** {disease_count}")
        if hidden_mut:
            lines.append(f"**Undiagnosed mutations:** {hidden_mut}")
        if hidden_dis:
            lines.append(f"**Undiagnosed diseases:** {hidden_dis}")
        if not lines:
            lines.append("No known conditions.")
        embed = discord.Embed(title=f"Patient Room — {p.name}", description="\n".join(lines))
        embed.set_footer(
            text=(
                f"Treat Injury: reduces injury persistence  •  "
                f"Diagnose Injuries: ${get_diagnose_injuries_cost()} — reveals hidden injuries  •  "
                f"Diagnose Mutations: ${get_diagnose_mutations_cost()} — reveals hidden mutations"
            )
        )
        return embed

    async def _on_treat(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        injury_instances = await get_pooch_injury_instances(self._pooch.id)
        if not injury_instances:
            re = InteractionResponder(interaction, ephemeral=True)
            await re.reply(content=f"{self._pooch.name} has no injuries to treat.")
            return
        view = _TreatInjurySelectView(
            owner_discord_id=self._owner_id, pooch=self._pooch, injury_instances=injury_instances
        )
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_diagnose_injuries(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        success, error, revealed = await diagnose_injuries(self._owner_id, self._pooch.id)
        if not success:
            await re.reply(content=f"Diagnosis failed: {error}")
            return
        lines = []
        if len(revealed) < sum(1 for pi in self._pooch.injuries if not pi.visible):
            lines.append("The doctors weren't able to fully diagnose your pooch.")
        if revealed:
            lines.append(f"**Revealed injuries on {self._pooch.name}:** {', '.join(revealed)}")
        else:
            lines.append(f"No hidden injuries were found on {self._pooch.name}.")
        await re.reply(content="\n".join(lines))

    async def _on_diagnose_mutations(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        hidden_before = sum(1 for pm in self._pooch.mutations if not pm.visible)
        success, error, revealed = await diagnose_mutations(self._owner_id, self._pooch.id)
        if not success:
            await re.reply(content=f"Diagnosis failed: {error}")
            return
        lines = []
        if len(revealed) < hidden_before:
            lines.append("The doctors weren't able to fully diagnose your pooch.")
        if revealed:
            lines.append(f"**Revealed mutations on {self._pooch.name}:** {', '.join(revealed)}")
        else:
            lines.append(f"No hidden mutations were found on {self._pooch.name}.")
        await re.reply(content="\n".join(lines))

    async def _on_treat_disease(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        disease_instances = await get_pooch_disease_instances(self._pooch.id)
        if not disease_instances:
            re = InteractionResponder(interaction, ephemeral=True)
            await re.reply(content=f"{self._pooch.name} has no diseases to treat.")
            return
        view = _TreatDiseaseSelectView(
            owner_discord_id=self._owner_id, pooch=self._pooch, disease_instances=disease_instances
        )
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_diagnose_diseases(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        success, error, revealed = await diagnose_diseases(self._owner_id, self._pooch.id)
        if not success:
            await re.reply(content=f"Diagnosis failed: {error}")
            return
        lines = []
        if len(revealed) < sum(1 for pd in self._pooch.diseases if not pd.visible):
            lines.append("The doctors weren't able to fully diagnose your pooch.")
        if revealed:
            lines.append(f"**Revealed diseases on {self._pooch.name}:** {', '.join(revealed)}")
        else:
            lines.append(f"No hidden diseases were found on {self._pooch.name}.")
        await re.reply(content="\n".join(lines))

    async def _on_medical_exam(self, interaction: discord.Interaction):
        re = InteractionResponder(interaction, ephemeral=True)
        success, error, report = await medical_exam(self._owner_id, self._pooch)
        if not success:
            await re.reply(content=f"Medical exam failed: {error}")
            return
        embed = discord.Embed(title=f"Medical Exam — {self._pooch.name}")
        lines = [f"**{stat}:** {rating}" for stat, rating in report.items()]
        embed.description = "\n".join(lines)
        await re.reply(embed=embed)


class _TreatInjurySelectView(View):
    def __init__(self, owner_discord_id: int, pooch: Pooch, injury_instances: list, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id
        self._pooch = pooch
        self._injury_instances = injury_instances
        self._selected_pi: Optional[object] = None

        options = []
        for pi in injury_instances[:DISCORD_SELECT_MAX_OPTIONS]:
            injury = pi.injury
            cost = get_treatment_cost(injury.severity)
            label = get_public_injury_label(pi)
            if is_injury_treated_today(pi):
                label += " (treated today)"
            desc = f"${cost} · Severity: {injury.severity.capitalize()}"
            if pi.persistence is not None:
                desc += f" · Persistence: {pi.persistence}"
            options.append(
                discord.SelectOption(
                    label=label[:DISCORD_LABEL_MAX_LENGTH],
                    value=str(pi.id),
                    description=desc[:DISCORD_DESCRIPTION_MAX_LENGTH],
                )
            )

        select = Select(placeholder="Select an injury to treat", options=options, min_values=1, max_values=1)
        select.callback = self._on_injury_select
        self._select = select
        self.add_item(select)

        self._treat_button = Button(label="Treat", style=discord.ButtonStyle.success, disabled=True, row=1)
        self._treat_button.callback = self._on_treat
        self.add_item(self._treat_button)

    async def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"Treat {self._pooch.name}'s Injuries")
        lines = []
        for pi in self._injury_instances:
            cost = get_treatment_cost(pi.injury.severity)
            if is_injury_treated_today(pi):
                status = " *(treated today)*"
            else:
                status = " *(treated)*" if pi.treated else ""
            persistence_str = f", persistence: {pi.persistence}" if pi.persistence is not None else ""
            lines.append(f"**{get_public_injury_label(pi)}**{status} — ${cost}{persistence_str}")
        embed.description = "\n".join(lines) if lines else "No injuries."
        embed.set_footer(text="Treating reduces persistence. Once per injury per day.")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def _on_injury_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        pi_id = int(self._select.values[0])
        pi = next((pi for pi in self._injury_instances if pi.id == pi_id), None)
        if pi is None:
            return
        self._selected_pi = pi
        self._treat_button.disabled = False
        for opt in self._select.options:
            opt.default = opt.value == str(pi_id)
        await r.edit(view=self)

    async def _on_treat(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected_pi is None:
            return
        success, message, cost = await treat_injury(self._owner_id, self._selected_pi.id)
        if not success:
            re = InteractionResponder(interaction, ephemeral=True)
            await re.reply(content=f"Treatment failed: {message}")
            return
        # Refresh injury instances and rebuild embed
        self._injury_instances = await get_pooch_injury_instances(self._pooch.id)
        embed = await self.build_embed()
        self._selected_pi = None
        self._treat_button.disabled = True
        for opt in self._select.options:
            opt.default = False
        await r.edit(embed=embed, view=self)
        re = InteractionResponder(interaction, ephemeral=True)
        await re.reply(content=f"Treated **{self._pooch.name}**. {message}")


class _TreatDiseaseSelectView(View):
    def __init__(self, owner_discord_id: int, pooch: Pooch, disease_instances: list, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id
        self._pooch = pooch
        self._disease_instances = disease_instances
        self._selected_pd: Optional[object] = None

        options = []
        for pd in disease_instances[:DISCORD_SELECT_MAX_OPTIONS]:
            disease = pd.disease
            cost = get_disease_treatment_cost()
            label = get_public_disease_label(pd)
            if pd.treated:
                label += " (treated)"
            if not disease.treatable:
                label += " (untreatable)"
            desc = f"${cost}"
            if not disease.curable:
                desc += " · Incurable"
            options.append(
                discord.SelectOption(
                    label=label[:DISCORD_LABEL_MAX_LENGTH],
                    value=str(pd.id),
                    description=desc[:DISCORD_DESCRIPTION_MAX_LENGTH],
                )
            )

        select = Select(placeholder="Select a disease to treat", options=options, min_values=1, max_values=1)
        select.callback = self._on_disease_select
        self._select = select
        self.add_item(select)

        self._treat_button = Button(label="Treat", style=discord.ButtonStyle.success, disabled=True, row=1)
        self._treat_button.callback = self._on_treat
        self.add_item(self._treat_button)

    async def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"Treat {self._pooch.name}'s Diseases")
        lines = []
        cost = get_disease_treatment_cost()
        for pd in self._disease_instances:
            disease = pd.disease
            status = " *(treated)*" if pd.treated else ""
            treatable = "" if disease.treatable else " *(untreatable)*"
            curable = "" if disease.curable else " *(incurable)*"
            lines.append(f"**{get_public_disease_label(pd)}**{status}{treatable}{curable} — ${cost}")
        embed.description = "\n".join(lines) if lines else "No diseases."
        embed.set_footer(text="Treating boosts recovery chance. Untreatable/incurable diseases cannot be cured.")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id

    async def _on_disease_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        pd_id = int(self._select.values[0])
        pd = next((pd for pd in self._disease_instances if pd.id == pd_id), None)
        if pd is None:
            return
        self._selected_pd = pd
        self._treat_button.disabled = False
        for opt in self._select.options:
            opt.default = opt.value == str(pd_id)
        await r.edit(view=self)

    async def _on_treat(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected_pd is None:
            return
        success, message, cost = await treat_disease(self._owner_id, self._selected_pd.id)
        if not success:
            re = InteractionResponder(interaction, ephemeral=True)
            await re.reply(content=f"Treatment failed: {message}")
            return
        self._disease_instances = await get_pooch_disease_instances(self._pooch.id)
        embed = await self.build_embed()
        self._selected_pd = None
        self._treat_button.disabled = True
        for opt in self._select.options:
            opt.default = False
        await r.edit(embed=embed, view=self)
        re = InteractionResponder(interaction, ephemeral=True)
        await re.reply(content=f"Treated **{self._pooch.name}**. {message}")


class InjuryListPageSource(PageSource):
    def __init__(self):
        self._injuries: list[Injury] = []

    async def load(self):
        self._injuries = await list_all_injuries()

    def page_count(self) -> int:
        return max(ceil(len(self._injuries) / PAGE_SIZE), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._injuries:
            return "Injuries:", discord.Embed(title="Injuries", description="No injuries found.")

        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = self._injuries[start:end]

        total_pages = self.page_count()
        embed = discord.Embed(title=f"Injuries ({page_index + 1}/{total_pages})")
        embed.description = "\n".join(f"{start + i + 1}. {inj.name}" for i, inj in enumerate(page_items))

        controls = InjuryDropdownControls(
            injuries=[InjuryOption(injury=inj, label=inj.name) for inj in page_items],
            placeholder="Select an injury (this page)",
        )
        controls.attach(view, row=1)

        return "Injuries:", embed


class _ListDiseasesButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="List Diseases", style=discord.ButtonStyle.primary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        source = DiseaseListPageSource()
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await r.reply(content=content, embed=embed, view=view)


class DiseaseListPageSource(PageSource):
    def __init__(self):
        self._diseases: list[Disease] = []

    async def load(self):
        self._diseases = await list_all_diseases()

    def page_count(self) -> int:
        return max(ceil(len(self._diseases) / PAGE_SIZE), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._diseases:
            return "Diseases:", discord.Embed(title="Diseases", description="No diseases found.")

        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = self._diseases[start:end]

        total_pages = self.page_count()
        embed = discord.Embed(title=f"Diseases ({page_index + 1}/{total_pages})")
        embed.description = "\n".join(f"{start + i + 1}. {d.name}" for i, d in enumerate(page_items))

        controls = DiseaseDropdownControls(
            diseases=[DiseaseOption(disease=d, label=d.name) for d in page_items],
            placeholder="Select a disease (this page)",
        )
        controls.attach(view, row=1)

        return "Diseases:", embed
