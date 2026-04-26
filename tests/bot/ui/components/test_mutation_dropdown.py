"""Contract tests for src/bot/ui/components/mutation_dropdown.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.components import (
    MutationDropdownControls,
    MutationOption,
    build_mutation_info_embed,
)


def _make_mutation(
    id=1,
    name="Cataracts",
    alt_name="Cat eyes",
    category="blindness",
    description="Vision loss.",
    heritability=0.5,
    health_impact="moderate_negative",
    rarity="uncommon",
    affects_females=True,
    affects_males=True,
):
    from src.game.models.mutation import Mutation

    return Mutation(
        id=id,
        name=name,
        alt_name=alt_name,
        category=category,
        description=description,
        heritability=heritability,
        health_impact=health_impact,
        rarity=rarity,
        affects_females=affects_females,
        affects_males=affects_males,
    )


@pytest.mark.contract
class TestBuildMutationInfoEmbed:
    def test_basic_embed(self):
        mutation = _make_mutation()
        embed = build_mutation_info_embed(mutation)
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Cataracts"

    def test_embed_fields(self):
        mutation = _make_mutation(heritability=0.75)
        embed = build_mutation_info_embed(mutation)
        field_names = [f.name for f in embed.fields]
        assert "Also Known As" in field_names
        assert "Category" in field_names
        assert "Rarity" in field_names
        assert "Health Impact" in field_names
        assert "Heritability" in field_names
        assert "Affects" in field_names

    def test_heritability_displayed_as_percent(self):
        mutation = _make_mutation(heritability=0.75)
        embed = build_mutation_info_embed(mutation)
        heritability_field = next(f for f in embed.fields if f.name == "Heritability")
        assert "75%" in heritability_field.value

    def test_affects_both(self):
        mutation = _make_mutation(affects_females=True, affects_males=True)
        embed = build_mutation_info_embed(mutation)
        affects_field = next(f for f in embed.fields if f.name == "Affects")
        assert "Females" in affects_field.value
        assert "Males" in affects_field.value

    def test_affects_none(self):
        mutation = _make_mutation(affects_females=False, affects_males=False)
        embed = build_mutation_info_embed(mutation)
        affects_field = next(f for f in embed.fields if f.name == "Affects")
        assert affects_field.value == "None"

    def test_no_alt_name_shows_dash(self):
        mutation = _make_mutation(alt_name="")
        embed = build_mutation_info_embed(mutation)
        also_known = next(f for f in embed.fields if f.name == "Also Known As")
        assert also_known.value == "\u2014"


@pytest.mark.contract
class TestMutationDropdownControls:
    def test_empty_mutations(self):
        controls = MutationDropdownControls(mutations=[])
        assert controls.select.disabled is True
        assert controls.info_button.disabled is True

    def test_with_mutations(self):
        mutation = _make_mutation(id=1, name="Sickle Cell")
        controls = MutationDropdownControls(mutations=[MutationOption(mutation=mutation, label="Sickle Cell")])
        assert controls.select.disabled is False
        assert controls.info_button.disabled is True

    async def test_attach_adds_items(self):
        mutation = _make_mutation()
        controls = MutationDropdownControls(mutations=[MutationOption(mutation=mutation, label="Test")])
        view = discord.ui.View()
        controls.attach(view, row=0)
        assert len(view.children) >= 2

    async def test_select_callback_enables_info(self):
        mutation = _make_mutation(id=1, name="Brittle Bones")
        controls = MutationDropdownControls(mutations=[MutationOption(mutation=mutation, label="Brittle Bones")])
        view = discord.ui.View()
        controls.attach(view, row=0)

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.edit_message = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["1"])),
            patch("src.bot.ui.components.mutation_dropdown.edit_interaction", new_callable=AsyncMock),
        ):
            await controls._on_select(interaction)

        assert controls.selected is not None
        assert controls.selected.name == "Brittle Bones"
        assert controls.info_button.disabled is False

    async def test_info_button_sends_embed(self):
        mutation = _make_mutation(id=1, name="Gigantism")
        controls = MutationDropdownControls(mutations=[MutationOption(mutation=mutation, label="Gigantism")])
        controls.selected = mutation

        interaction = MagicMock()

        with patch(
            "src.bot.ui.components.mutation_dropdown.reply_to_interacted_message", new_callable=AsyncMock
        ) as mock_reply:
            await controls._on_info(interaction)
            mock_reply.assert_called_once()
            embed_arg = mock_reply.call_args[1]["embed"]
            assert embed_arg.title == "Gigantism"
