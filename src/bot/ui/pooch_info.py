from typing import TYPE_CHECKING, Optional, Sequence

import discord
from discord.ui import Button, Select, View

from bot.constants import VIEW_TIMEOUT
from bot.ui.util import edit_interaction, mention, reply_to_interacted_message
from game import get_pooch_family

if TYPE_CHECKING:
    from game.model import Mutation, Owner, Pooch, PoochBreedInfo, Server


class _FamilySelect(Select):
    def __init__(self, members: Sequence[Pooch], *, placeholder: str, kind: str):
        super().__init__(
            placeholder=placeholder,
            options=[discord.SelectOption(label=member.name, value=str(member.id)) for member in members],
            min_values=1,
            max_values=1,
        )
        self.kind = kind
        self._members = list(members)


class _BreedSelect(Select):
    def __init__(self, breeds: Sequence["PoochBreedInfo"], *, placeholder: str = "Select a breed"):
        super().__init__(
            placeholder=placeholder,
            options=[
                discord.SelectOption(
                    label=f"{pb.breed.name} ({pb.relative_weight:.0%})",
                    value=str(pb.breed.id),
                )
                for pb in breeds
            ],
            min_values=1,
            max_values=1,
        )
        self._breeds = list(breeds)


class _MutationSelect(Select):
    def __init__(self, mutations: Sequence["Mutation"], *, placeholder: str = "Select a mutation"):
        super().__init__(
            placeholder=placeholder,
            options=[discord.SelectOption(label=m.name, value=str(m.id)) for m in mutations],
            min_values=1,
            max_values=1,
        )
        self._mutations = list(mutations)


class PoochInfoView(View):
    def __init__(self, *, server: Server, pooch: Pooch, owner: Optional[Owner], timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server = server
        self.pooch = pooch
        self.owner = owner
        self._selected: dict[str, Optional[Pooch]] = {"parents": None, "children": None, "siblings": None}

        self.parent_info_button = Button(label="Parent Info", style=discord.ButtonStyle.primary, disabled=True)
        self.child_info_button = Button(label="Child Info", style=discord.ButtonStyle.primary, disabled=True)
        self.sibling_info_button = Button(label="Sibling Info", style=discord.ButtonStyle.primary, disabled=True)

        self.parent_info_button.callback = self._open_parent  # type: ignore
        self.child_info_button.callback = self._open_child  # type: ignore
        self.sibling_info_button.callback = self._open_sibling  # type: ignore

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner is None:
            return True
        return interaction.user.id == self.owner.discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._selected = {"parents": None, "children": None, "siblings": None}

        family = await get_pooch_family(self.pooch.id)

        embed = discord.Embed(title=self.pooch.name)
        embed.add_field(name="Age", value=str(self.pooch.age), inline=True)
        embed.add_field(name="Sex", value=self.pooch.sex.capitalize(), inline=True)
        embed.add_field(name="Health", value=str(self.pooch.health), inline=True)

        embed.add_field(
            name="Owner",
            value=(
                mention(self.pooch.owner_discord_id)
                if self.pooch.owner_discord_id
                else (self.pooch.vendor.name if self.pooch.vendor is not None else "Nobody")
            ),
            inline=True,
        )
        embed.add_field(name="Status", value=self.pooch.status.capitalize(), inline=True)
        embed.add_field(name="Birthday", value=str(self.pooch.birthday.date()), inline=True)

        # Breeds & mutations
        breed_names = ", ".join(f"{pb.breed.name} ({pb.relative_weight:.0%})" for pb in self.pooch.breeds) or "None"
        mutation_names = ", ".join(m.name for m in self.pooch.mutations) or "None"
        embed.add_field(name="Breeds", value=breed_names, inline=False)
        embed.add_field(name="Mutations", value=mutation_names, inline=False)

        parents = family.get("parents", [])
        children = family.get("children", [])
        siblings = family.get("siblings", [])

        embed.add_field(name="Parents", value=", ".join(parent.name for parent in parents) or "None", inline=False)
        embed.add_field(name="Children", value=", ".join(child.name for child in children) or "None", inline=False)
        embed.add_field(name="Siblings", value=", ".join(sibling.name for sibling in siblings) or "None", inline=False)

        row_cursor = 0

        if parents:
            select = _FamilySelect(parents, placeholder="Select a parent", kind="parents")
            select.callback = self._on_family_selected  # type: ignore
            select.row = row_cursor
            self.add_item(select)
            self.parent_info_button.disabled = True
            self.parent_info_button.row = row_cursor + 1
            self.add_item(self.parent_info_button)
            row_cursor += 2

        if children:
            select = _FamilySelect(children, placeholder="Select a child", kind="children")
            select.callback = self._on_family_selected  # type: ignore
            select.row = row_cursor
            self.add_item(select)
            self.child_info_button.disabled = True
            self.child_info_button.row = row_cursor + 1
            self.add_item(self.child_info_button)
            row_cursor += 2

        if siblings:
            select = _FamilySelect(siblings, placeholder="Select a sibling", kind="siblings")
            select.callback = self._on_family_selected  # type: ignore
            select.row = row_cursor
            self.add_item(select)
            self.sibling_info_button.disabled = True
            self.sibling_info_button.row = row_cursor + 1
            self.add_item(self.sibling_info_button)
            row_cursor += 2

        # Breed & mutation info selectors
        if self.pooch.breeds:
            breed_select = _BreedSelect(self.pooch.breeds)
            breed_select.callback = self._on_breed_selected  # type: ignore
            breed_select.row = row_cursor
            self.add_item(breed_select)
            row_cursor += 1

        if self.pooch.mutations:
            mutation_select = _MutationSelect(self.pooch.mutations)
            mutation_select.callback = self._on_mutation_selected  # type: ignore
            mutation_select.row = row_cursor
            self.add_item(mutation_select)
            row_cursor += 1

        return embed

    async def _on_breed_selected(self, interaction: discord.Interaction):
        selected_value = str(interaction.data["values"][0])  # type: ignore
        selected_id = int(selected_value)

        selected = next((pb for pb in self.pooch.breeds if pb.breed.id == selected_id), None)
        if selected is None:
            return

        # Keep the selection highlighted
        for item in self.children:
            if isinstance(item, _BreedSelect):
                for option in item.options:
                    option.default = option.value == selected_value

        breed = selected.breed
        embed = discord.Embed(title=breed.name, description=(breed.description or "None"))
        embed.add_field(name="Also Known As", value=breed.alt_name or "None", inline=True)
        embed.add_field(name="Category", value=breed.category or "None", inline=True)
        embed.add_field(name="Rarity", value=str(breed.rarity).capitalize(), inline=True)
        embed.add_field(name="Relative Weight", value=f"{selected.relative_weight:.0%}", inline=True)
        embed.add_field(name="Description", value=breed.description or "None", inline=False)

        if not interaction.response.is_done():
            await interaction.response.defer()
        await interaction.followup.send(embed=embed)
        await edit_interaction(interaction, view=self)

    async def _on_mutation_selected(self, interaction: discord.Interaction):
        selected_value = str(interaction.data["values"][0])  # type: ignore
        selected_id = int(selected_value)

        selected = next((m for m in self.pooch.mutations if m.id == selected_id), None)
        if selected is None:
            return

        # Keep the selection highlighted
        for item in self.children:
            if isinstance(item, _MutationSelect):
                for option in item.options:
                    option.default = option.value == selected_value

        mutation = selected
        embed = discord.Embed(title=mutation.name, description=(mutation.description or "None"))
        embed.add_field(name="Also Known As", value=mutation.alt_name or "None", inline=True)
        embed.add_field(name="Category", value=mutation.category or "None", inline=True)
        embed.add_field(name="Rarity", value=str(mutation.rarity).capitalize(), inline=True)
        embed.add_field(name="Heritability", value=f"{mutation.heritability:.0%}", inline=True)
        embed.add_field(name="Health Impact", value=str(mutation.health_impact).capitalize(), inline=True)
        embed.add_field(
            name="Affects",
            value=(
                ", ".join(part for part, ok in (("Females", mutation.affects_females), ("Males", mutation.affects_males)) if ok)
                or "None"
            ),
            inline=True,
        )

        if not interaction.response.is_done():
            await interaction.response.defer()
        await interaction.followup.send(embed=embed)
        await edit_interaction(interaction, view=self)

    async def _on_family_selected(self, interaction: discord.Interaction):
        selected_value = str(interaction.data["values"][0])  # type: ignore

        fired_select: Optional[_FamilySelect] = None
        for item in self.children:
            if isinstance(item, _FamilySelect) and item.values and item.values[0] == selected_value:
                fired_select = item
                break
        if fired_select is None:
            return

        selected_id = int(selected_value)
        selected_member = next((member for member in fired_select._members if member.id == selected_id), None)
        if selected_member is None:
            return

        self._selected[fired_select.kind] = selected_member

        # Make sure the dropdown selection persists between refreshes
        for option in fired_select.options:
            option.default = option.value == selected_value

        if fired_select.kind == "parents":
            self.parent_info_button.disabled = False
        elif fired_select.kind == "children":
            self.child_info_button.disabled = False
        elif fired_select.kind == "siblings":
            self.sibling_info_button.disabled = False

        await edit_interaction(interaction, view=self)

    async def _open_parent(self, interaction: discord.Interaction):
        pooch = self._selected.get("parents")
        if pooch is None:
            return
        view = PoochInfoView(server=self.server, pooch=pooch, owner=self.owner)
        embed = await view.build_embed()
        await reply_to_interacted_message(interaction, embed=embed, view=view)

    async def _open_child(self, interaction: discord.Interaction):
        pooch = self._selected.get("children")
        if pooch is None:
            return
        view = PoochInfoView(server=self.server, pooch=pooch, owner=self.owner)
        embed = await view.build_embed()
        await reply_to_interacted_message(interaction, embed=embed, view=view)

    async def _open_sibling(self, interaction: discord.Interaction):
        pooch = self._selected.get("siblings")
        if pooch is None:
            return
        view = PoochInfoView(server=self.server, pooch=pooch, owner=self.owner)
        embed = await view.build_embed()
        await reply_to_interacted_message(interaction, embed=embed, view=view)
