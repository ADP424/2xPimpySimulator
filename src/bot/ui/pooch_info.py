import discord
from discord.ui import View, Select, Button
from typing import Optional, Sequence

from game.main import get_pooch_by_id, get_pooch_family
from bot.ui.util import edit_interaction


def _mention(discord_id: int) -> str:
    return f"<@{discord_id}>"


class _FamilySelect(Select):
    def __init__(self, members: Sequence, *, placeholder: str, kind: str):
        super().__init__(
            placeholder=placeholder,
            options=[
                discord.SelectOption(label=getattr(m, "name", "Unknown"), value=str(getattr(m, "id"))) for m in members
            ],
            min_values=1,
            max_values=1,
        )
        self.kind = kind


class PoochInfoView(View):
    def __init__(self, *, server_id: int, pooch_id: int, owner_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.server_id = server_id
        self.pooch_id = pooch_id
        self.owner_id = owner_id
        self._selected: dict[str, Optional[int]] = {"parents": None, "children": None, "siblings": None}

        self.parent_info_btn = Button(label="Parent Info", style=discord.ButtonStyle.primary, disabled=True)
        self.child_info_btn = Button(label="Child Info", style=discord.ButtonStyle.primary, disabled=True)
        self.sibling_info_btn = Button(label="Sibling Info", style=discord.ButtonStyle.primary, disabled=True)

        self.parent_info_btn.callback = self._open_parent  # type: ignore
        self.child_info_btn.callback = self._open_child  # type: ignore
        self.sibling_info_btn.callback = self._open_sibling  # type: ignore

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._selected = {"parents": None, "children": None, "siblings": None}

        pooch = await get_pooch_by_id(self.server_id, self.pooch_id)
        family = await get_pooch_family(self.server_id, self.pooch_id)

        embed = discord.Embed(title=pooch.name)
        embed.add_field(name="Age", value=str(pooch.age), inline=True)
        embed.add_field(name="Sex", value=str(pooch.sex), inline=True)
        embed.add_field(name="Health", value=str(pooch.health), inline=True)

        embed.add_field(
            name="Owner",
            value=_mention(int(pooch.owner_discord_id)) if pooch.owner_discord_id else "Unknown",
            inline=True,
        )
        embed.add_field(name="Status", value=str(pooch.status), inline=True)
        embed.add_field(name="Birthday", value=str(pooch.birthday), inline=True)

        parents = family.get("parents", [])
        children = family.get("children", [])
        siblings = family.get("siblings", [])

        embed.add_field(name="Parents", value=", ".join(p.name for p in parents) or "None", inline=False)
        embed.add_field(name="Children", value=", ".join(c.name for c in children) or "None", inline=False)
        embed.add_field(name="Siblings", value=", ".join(s.name for s in siblings) or "None", inline=False)

        if parents:
            sel = _FamilySelect(parents, placeholder="Select a parent", kind="parents")
            sel.callback = self._on_family_selected  # type: ignore
            self.add_item(sel)
            self.parent_info_btn.disabled = True
            self.add_item(self.parent_info_btn)

        if children:
            sel = _FamilySelect(children, placeholder="Select a child", kind="children")
            sel.callback = self._on_family_selected  # type: ignore
            self.add_item(sel)
            self.child_info_btn.disabled = True
            self.add_item(self.child_info_btn)

        if siblings:
            sel = _FamilySelect(siblings, placeholder="Select a sibling", kind="siblings")
            sel.callback = self._on_family_selected  # type: ignore
            self.add_item(sel)
            self.sibling_info_btn.disabled = True
            self.add_item(self.sibling_info_btn)

        return embed

    async def _on_family_selected(self, interaction: discord.Interaction):
        selected_value = int(interaction.data["values"][0])  # type: ignore

        fired_kind = None
        for item in self.children:
            if isinstance(item, _FamilySelect) and item.values and item.values[0] == str(selected_value):
                fired_kind = item.kind
                break
        if fired_kind is None:
            return

        self._selected[fired_kind] = selected_value

        if fired_kind == "parents":
            self.parent_info_btn.disabled = False
        elif fired_kind == "children":
            self.child_info_btn.disabled = False
        elif fired_kind == "siblings":
            self.sibling_info_btn.disabled = False

        await edit_interaction(interaction, view=self)

    async def _open_parent(self, interaction: discord.Interaction):
        pid = self._selected.get("parents")
        if pid is None:
            return
        self.pooch_id = pid
        embed = await self.build_embed()
        await edit_interaction(interaction, embed=embed, view=self)

    async def _open_child(self, interaction: discord.Interaction):
        pid = self._selected.get("children")
        if pid is None:
            return
        self.pooch_id = pid
        embed = await self.build_embed()
        await edit_interaction(interaction, embed=embed, view=self)

    async def _open_sibling(self, interaction: discord.Interaction):
        pid = self._selected.get("siblings")
        if pid is None:
            return
        self.pooch_id = pid
        embed = await self.build_embed()
        await edit_interaction(interaction, embed=embed, view=self)
