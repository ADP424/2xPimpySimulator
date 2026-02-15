import discord
from discord.ui import View, Select, Button
from typing import TYPE_CHECKING, Optional, Sequence

from game import get_pooch_family
from bot.ui.util import edit_interaction, mention

if TYPE_CHECKING:
    from game.model import Server, Pooch, Owner


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


class PoochInfoView(View):
    def __init__(self, *, server: Server, pooch: Pooch, owner: Optional[Owner], timeout: float = 300):
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
            value=mention(self.pooch.owner_discord_id) if self.pooch.owner_discord_id else "Nobody",
            inline=True,
        )
        embed.add_field(name="Status", value=self.pooch.status.capitalize(), inline=True)
        embed.add_field(name="Birthday", value=str(self.pooch.birthday.date()), inline=True)

        parents = family.get("parents", [])
        children = family.get("children", [])
        siblings = family.get("siblings", [])

        embed.add_field(name="Parents", value=", ".join(parent.name for parent in parents) or "None", inline=False)
        embed.add_field(name="Children", value=", ".join(child.name for child in children) or "None", inline=False)
        embed.add_field(name="Siblings", value=", ".join(sibling.name for sibling in siblings) or "None", inline=False)

        if parents:
            select = _FamilySelect(parents, placeholder="Select a parent", kind="parents")
            select.callback = self._on_family_selected  # type: ignore
            self.add_item(select)
            self.parent_info_button.disabled = True
            self.add_item(self.parent_info_button)

        if children:
            select = _FamilySelect(children, placeholder="Select a child", kind="children")
            select.callback = self._on_family_selected  # type: ignore
            self.add_item(select)
            self.child_info_button.disabled = True
            self.add_item(self.child_info_button)

        if siblings:
            select = _FamilySelect(siblings, placeholder="Select a sibling", kind="siblings")
            select.callback = self._on_family_selected  # type: ignore
            self.add_item(select)
            self.sibling_info_button.disabled = True
            self.add_item(self.sibling_info_button)

        return embed

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
        self.pooch = pooch
        embed = await self.build_embed()
        await edit_interaction(interaction, embed=embed, view=self)

    async def _open_child(self, interaction: discord.Interaction):
        pooch = self._selected.get("children")
        if pooch is None:
            return
        self.pooch = pooch
        embed = await self.build_embed()
        await edit_interaction(interaction, embed=embed, view=self)

    async def _open_sibling(self, interaction: discord.Interaction):
        pooch = self._selected.get("siblings")
        if pooch is None:
            return
        self.pooch = pooch
        embed = await self.build_embed()
        await edit_interaction(interaction, embed=embed, view=self)
