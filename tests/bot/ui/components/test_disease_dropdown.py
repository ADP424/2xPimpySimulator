"""Tests for src/bot/ui/components/disease_dropdown.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.components import (
    DiseaseDropdownControls,
    DiseaseOption,
    build_disease_info_embed,
)
from src.game.models.disease import Disease


def _make_disease(
    id=1,
    name="Kennel Cough",
    category="Viral",
    description="A respiratory infection.",
    health_impact="harmful",
    contagion_chance=0.5,
    sexually_transmitted=False,
    recovery_chance=0.3,
    treatable=True,
    curable=True,
    immunity_duration=30,
    heritability=0.1,
    seasons=None,
    season_contagion_modifiers=None,
    parameters=None,
    visible=True,
    invisible_messages=None,
    reveal_chance=1.0,
):
    return Disease(
        id=id,
        name=name,
        category=category,
        description=description,
        health_impact=health_impact,
        contagion_chance=contagion_chance,
        sexually_transmitted=sexually_transmitted,
        recovery_chance=recovery_chance,
        treatable=treatable,
        curable=curable,
        immunity_duration=immunity_duration,
        heritability=heritability,
        seasons=seasons,
        season_contagion_modifiers=season_contagion_modifiers,
        parameters=parameters or {},
        visible=visible,
        invisible_messages=invisible_messages,
        reveal_chance=reveal_chance,
    )


# ---------------------------------------------------------------------------
# build_disease_info_embed
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestBuildDiseaseInfoEmbed:
    def test_stat_effects(self):
        embed = build_disease_info_embed(_make_disease(parameters={"constitution_add": -3, "strength_add": -2}))
        stat_effects = next(f for f in embed.fields if f.name == "Stat Effects")
        assert stat_effects.value == "▼ Strength -2\n▼ Constitution -3"

    def test_basic_embed(self):
        disease = _make_disease()
        embed = build_disease_info_embed(disease)
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Kennel Cough"

    def test_shows_description(self):
        disease = _make_disease(description="A nasty respiratory bug.")
        embed = build_disease_info_embed(disease)
        assert embed.description == "A nasty respiratory bug."

    def test_no_description_shows_default(self):
        disease = _make_disease(description="")
        embed = build_disease_info_embed(disease)
        assert embed.description == "No description."

    def test_shows_health_impact(self):
        disease = _make_disease(health_impact="severe")
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Health Impact" in field_names
        hi_field = next(f for f in embed.fields if f.name == "Health Impact")
        assert "Severe" in hi_field.value

    def test_shows_category(self):
        disease = _make_disease(category="Parasitic")
        embed = build_disease_info_embed(disease)
        cat_field = next(f for f in embed.fields if f.name == "Category")
        assert cat_field.value == "Parasitic"

    def test_shows_contagion_info_percentage(self):
        disease = _make_disease(contagion_chance=0.75)
        embed = build_disease_info_embed(disease)
        contagious_field = next(f for f in embed.fields if f.name == "Contagious")
        assert "75%" in contagious_field.value

    def test_shows_contagion_no_when_zero(self):
        disease = _make_disease(contagion_chance=0.0)
        embed = build_disease_info_embed(disease)
        contagious_field = next(f for f in embed.fields if f.name == "Contagious")
        assert contagious_field.value == "No"

    def test_shows_std_transmission(self):
        disease = _make_disease(sexually_transmitted=True)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Transmission" in field_names
        tx_field = next(f for f in embed.fields if f.name == "Transmission")
        assert "Sexually transmitted" in tx_field.value

    def test_no_transmission_field_when_not_std(self):
        disease = _make_disease(sexually_transmitted=False)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Transmission" not in field_names

    def test_shows_recovery_chance_percentage(self):
        disease = _make_disease(recovery_chance=0.25)
        embed = build_disease_info_embed(disease)
        recovery_field = next(f for f in embed.fields if f.name == "Recovery Chance")
        assert "25%" in recovery_field.value
        assert "/day" in recovery_field.value

    def test_shows_requires_treatment_when_zero_recovery(self):
        disease = _make_disease(recovery_chance=0.0, treatable=True)
        embed = build_disease_info_embed(disease)
        recovery_field = next(f for f in embed.fields if f.name == "Recovery Chance")
        assert "Requires treatment" in recovery_field.value

    def test_shows_none_recovery_when_untreatable_zero_chance(self):
        disease = _make_disease(recovery_chance=0.0, treatable=False)
        embed = build_disease_info_embed(disease)
        recovery_field = next(f for f in embed.fields if f.name == "Recovery Chance")
        assert recovery_field.value == "None"

    def test_shows_treatable_yes(self):
        disease = _make_disease(treatable=True)
        embed = build_disease_info_embed(disease)
        treat_field = next(f for f in embed.fields if f.name == "Treatable")
        assert treat_field.value == "Yes"

    def test_shows_treatable_no(self):
        disease = _make_disease(treatable=False)
        embed = build_disease_info_embed(disease)
        treat_field = next(f for f in embed.fields if f.name == "Treatable")
        assert treat_field.value == "No"

    def test_shows_curable_yes(self):
        disease = _make_disease(curable=True)
        embed = build_disease_info_embed(disease)
        cure_field = next(f for f in embed.fields if f.name == "Curable")
        assert cure_field.value == "Yes"

    def test_shows_curable_no_permanent(self):
        disease = _make_disease(curable=False)
        embed = build_disease_info_embed(disease)
        cure_field = next(f for f in embed.fields if f.name == "Curable")
        assert "permanent" in cure_field.value.lower()

    def test_shows_heritability(self):
        disease = _make_disease(heritability=0.5)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Heritability" in field_names
        h_field = next(f for f in embed.fields if f.name == "Heritability")
        assert "50%" in h_field.value

    def test_no_heritability_field_when_zero(self):
        disease = _make_disease(heritability=0.0)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Heritability" not in field_names

    def test_shows_seasons(self):
        disease = _make_disease(seasons=["winter", "autumn"])
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Seasons" in field_names
        s_field = next(f for f in embed.fields if f.name == "Seasons")
        assert "Winter" in s_field.value
        assert "Autumn" in s_field.value

    def test_no_seasons_field_when_none(self):
        disease = _make_disease(seasons=None)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Seasons" not in field_names

    def test_shows_immunity_duration(self):
        disease = _make_disease(immunity_duration=30)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Immunity After Recovery" in field_names
        imm_field = next(f for f in embed.fields if f.name == "Immunity After Recovery")
        assert "30 days" in imm_field.value

    def test_no_immunity_field_when_none(self):
        disease = _make_disease(immunity_duration=None)
        embed = build_disease_info_embed(disease)
        field_names = [f.name for f in embed.fields]
        assert "Immunity After Recovery" not in field_names


# ---------------------------------------------------------------------------
# DiseaseDropdownControls
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestDiseaseDropdownControls:
    def test_empty_diseases(self):
        controls = DiseaseDropdownControls(diseases=[])
        assert controls.select.disabled is True
        assert controls.info_button.disabled is True

    def test_with_diseases(self):
        disease = _make_disease(id=1, name="Distemper")
        controls = DiseaseDropdownControls(diseases=[DiseaseOption(disease=disease, label="Distemper")])
        assert controls.select.disabled is False
        assert controls.info_button.disabled is True

    async def test_attach_adds_items(self):
        disease = _make_disease()
        controls = DiseaseDropdownControls(diseases=[DiseaseOption(disease=disease, label="Test")])
        view = discord.ui.View()
        controls.attach(view, row=0)
        assert len(view.children) >= 2

    async def test_select_callback_enables_info(self):
        disease = _make_disease(id=1, name="Fleas")
        controls = DiseaseDropdownControls(diseases=[DiseaseOption(disease=disease, label="Fleas")])
        view = discord.ui.View()
        controls.attach(view, row=0)

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.edit_message = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()

        with (
            patch.object(
                type(controls.select),
                "values",
                new_callable=lambda: property(lambda self: ["1"]),
            ),
            patch(
                "src.bot.ui.components.disease_dropdown.edit_interaction",
                new_callable=AsyncMock,
            ),
        ):
            await controls._on_select(interaction)

        assert controls.selected is not None
        assert controls.selected.name == "Fleas"
        assert controls.info_button.disabled is False

    async def test_info_button_sends_embed(self):
        disease = _make_disease(id=1, name="Rabies")
        controls = DiseaseDropdownControls(diseases=[DiseaseOption(disease=disease, label="Rabies")])
        controls.selected = disease

        interaction = MagicMock()

        with patch(
            "src.bot.ui.components.disease_dropdown.reply_to_interacted_message",
            new_callable=AsyncMock,
        ) as mock_reply:
            await controls._on_info(interaction)
            mock_reply.assert_called_once()
            embed_arg = mock_reply.call_args[1]["embed"]
            assert embed_arg.title == "Rabies"

    async def test_select_none_disables_info(self):
        controls = DiseaseDropdownControls(diseases=[DiseaseOption(disease=_make_disease(), label="Test")])
        view = discord.ui.View()
        controls.attach(view, row=0)

        interaction = MagicMock()

        with (
            patch.object(
                type(controls.select),
                "values",
                new_callable=lambda: property(lambda self: ["__none__"]),
            ),
            patch(
                "src.bot.ui.components.disease_dropdown.edit_interaction",
                new_callable=AsyncMock,
            ),
        ):
            await controls._on_select(interaction)

        assert controls.selected is None
        assert controls.info_button.disabled is True

    def test_custom_placeholder(self):
        controls = DiseaseDropdownControls(diseases=[], placeholder="Pick a disease")
        assert controls.select.placeholder == "Pick a disease"

    async def test_info_button_noop_when_no_selection(self):
        controls = DiseaseDropdownControls(diseases=[])
        controls.selected = None
        interaction = MagicMock()
        # Should not raise and should not call reply
        with patch(
            "src.bot.ui.components.disease_dropdown.reply_to_interacted_message",
            new_callable=AsyncMock,
        ) as mock_reply:
            await controls._on_info(interaction)
            mock_reply.assert_not_called()
