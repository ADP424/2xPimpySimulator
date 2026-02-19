from __future__ import annotations

from math import ceil
from typing import Optional

import discord
from discord.ui import Button, View

from bot.constants import VIEW_TIMEOUT
from bot.ui.util import defer_interaction, reply_to_interacted_message
from game import list_all_breeds, list_all_mutations
from game.models import Breed, Mutation

from .components.breed_dropdown import BreedDropdownControls, BreedOption
from .components.mutation_dropdown import MutationDropdownControls, MutationOption
from .components.paginator import PageSource, PaginatorView

PAGE_SIZE = 10


class VetClinicView(View):
    def __init__(self, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self._owner_id = owner_discord_id

        self.add_item(_ListBreedsButton(owner_discord_id=owner_discord_id))
        self.add_item(_ListMutationsButton(owner_discord_id=owner_discord_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._owner_id


class _ListBreedsButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="List Breeds", style=discord.ButtonStyle.primary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        source = BreedListPageSource()
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await reply_to_interacted_message(
            interaction,
            content=content,
            embed=embed,
            view=view,
        )


class _ListMutationsButton(Button):
    def __init__(self, owner_discord_id: int):
        super().__init__(label="List Mutations", style=discord.ButtonStyle.primary, row=0)
        self._owner_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        await defer_interaction(interaction)
        source = MutationListPageSource()
        view = PaginatorView(source, owner_discord_id=self._owner_id)
        content, embed = await view.build_first_page()
        await reply_to_interacted_message(
            interaction,
            content=content,
            embed=embed,
            view=view,
        )


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
