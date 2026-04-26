"""Contract tests for src/bot/ui/vet_clinic.py."""

from math import ceil
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.vet_clinic import (
    BreedListPageSource,
    MutationListPageSource,
    VetClinicView,
)


def _make_breed(id=1, name="Poodle"):
    from src.game.models.breed import Breed

    return Breed(
        id=id,
        name=name,
        alt_name="",
        category="water_dog",
        description="A fancy dog.",
        rarity="common",
        min_size=30,
        max_size=50,
    )


def _make_mutation(id=1, name="Cataracts"):
    from src.game.models.mutation import Mutation

    return Mutation(
        id=id,
        name=name,
        alt_name="",
        category="blindness",
        description="Vision loss.",
        heritability=0.5,
        health_impact="moderate_negative",
        rarity="uncommon",
        affects_females=True,
        affects_males=True,
    )


@pytest.mark.contract
class TestVetClinicView:
    async def test_creates_view(self):
        view = VetClinicView(owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_list_breeds_button(self):
        view = VetClinicView(owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "List Breeds" for b in buttons)

    async def test_has_list_mutations_button(self):
        view = VetClinicView(owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "List Mutations" for b in buttons)

    async def test_interaction_check_owner_only(self):
        view = VetClinicView(owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False


@pytest.mark.contract
class TestBreedListPageSource:
    async def test_empty_breeds(self):
        with patch("src.bot.ui.vet_clinic.list_all_breeds", new_callable=AsyncMock, return_value=[]):
            source = BreedListPageSource()
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No breeds found" in embed.description

    async def test_breeds_pagination(self):
        breeds = [_make_breed(id=i, name=f"Breed{i}") for i in range(25)]
        with patch("src.bot.ui.vet_clinic.list_all_breeds", new_callable=AsyncMock, return_value=breeds):
            source = BreedListPageSource()
            await source.load()
            assert source.page_count() == ceil(25 / 10)

    async def test_render_page(self):
        breeds = [_make_breed(id=1, name="Labrador"), _make_breed(id=2, name="Pug")]
        with patch("src.bot.ui.vet_clinic.list_all_breeds", new_callable=AsyncMock, return_value=breeds):
            source = BreedListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Labrador" in embed.description
            assert "Pug" in embed.description


@pytest.mark.contract
class TestMutationListPageSource:
    async def test_empty_mutations(self):
        with patch("src.bot.ui.vet_clinic.list_all_mutations", new_callable=AsyncMock, return_value=[]):
            source = MutationListPageSource()
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No mutations found" in embed.description

    async def test_mutations_pagination(self):
        mutations = [_make_mutation(id=i, name=f"Mut{i}") for i in range(15)]
        with patch("src.bot.ui.vet_clinic.list_all_mutations", new_callable=AsyncMock, return_value=mutations):
            source = MutationListPageSource()
            await source.load()
            assert source.page_count() == ceil(15 / 10)

    async def test_render_page(self):
        mutations = [_make_mutation(id=1, name="Blindness")]
        with patch("src.bot.ui.vet_clinic.list_all_mutations", new_callable=AsyncMock, return_value=mutations):
            source = MutationListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Blindness" in embed.description
