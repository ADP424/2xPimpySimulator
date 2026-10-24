"""Tests for src/bot/ui/components/injury_dropdown.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.components import (
    InjuryDropdownControls,
    InjuryOption,
    build_injury_info_embed,
)


def _make_injury(
    id=1,
    name="Sprained Leg",
    description="A sprained leg.",
    health_impact="minor_negative",
    severity="minor",
    parameters=None,
    treated=None,
):
    injury = MagicMock()
    injury.id = id
    injury.name = name
    injury.description = description
    injury.health_impact = health_impact
    injury.severity = severity
    injury.parameters = parameters if parameters is not None else {}
    injury.treated = treated
    return injury


# ---------------------------------------------------------------------------
# build_injury_info_embed
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestBuildInjuryInfoEmbed:
    def test_stat_effects_and_stacks(self):
        injury = _make_injury(
            parameters={"strength_mult": 0.8, "stacks": [{"min_count": 2, "max_count": 2, "size_mult": 0.9}]}
        )
        embed = build_injury_info_embed(injury)
        fields = {f.name: f.value for f in embed.fields}
        assert fields["Stat Effects"] == "▼ Strength ×0.8"
        assert fields["Extra Stat Effects (with 2)"] == "▼ Size ×0.9"

    def test_no_stat_effects(self):
        embed = build_injury_info_embed(_make_injury())
        assert next(f for f in embed.fields if f.name == "Stat Effects").value == "None"

    def test_basic_embed(self):
        injury = _make_injury()
        embed = build_injury_info_embed(injury)
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Sprained Leg"

    def test_shows_description(self):
        injury = _make_injury(description="A nasty sprain.")
        embed = build_injury_info_embed(injury)
        assert embed.description == "A nasty sprain."

    def test_no_description_shows_default(self):
        injury = _make_injury(description="")
        embed = build_injury_info_embed(injury)
        assert embed.description == "No description."

    def test_shows_health_impact(self):
        injury = _make_injury(health_impact="moderate_negative")
        embed = build_injury_info_embed(injury)
        field_names = [f.name for f in embed.fields]
        assert "Health Impact" in field_names

    def test_shows_severity(self):
        injury = _make_injury(severity="major")
        embed = build_injury_info_embed(injury)
        field_names = [f.name for f in embed.fields]
        assert "Severity" in field_names
        sev_field = next(f for f in embed.fields if f.name == "Severity")
        assert "Major" in sev_field.value

    def test_shows_persistence_when_set(self):
        injury = _make_injury(parameters={"persistence": 3})
        embed = build_injury_info_embed(injury)
        field_names = [f.name for f in embed.fields]
        assert "Persistence" in field_names
        pers_field = next(f for f in embed.fields if f.name == "Persistence")
        assert "3" in pers_field.value

    def test_no_persistence_field_when_absent(self):
        injury = _make_injury(parameters={})
        embed = build_injury_info_embed(injury)
        field_names = [f.name for f in embed.fields]
        assert "Persistence" not in field_names

    def test_shows_treated_description(self):
        injury = _make_injury(treated={"description": "Apply bandage"})
        embed = build_injury_info_embed(injury)
        field_names = [f.name for f in embed.fields]
        assert "Treated" in field_names
        treated_field = next(f for f in embed.fields if f.name == "Treated")
        assert "Apply bandage" in treated_field.value

    def test_shows_treated_health_impact(self):
        injury = _make_injury(treated={"health_impact": "minor_negative", "description": "Splint"})
        embed = build_injury_info_embed(injury)
        treated_field = next(f for f in embed.fields if f.name == "Treated")
        assert "Minor negative" in treated_field.value

    def test_no_treated_field_when_none(self):
        injury = _make_injury(treated=None)
        embed = build_injury_info_embed(injury)
        field_names = [f.name for f in embed.fields]
        assert "Treated" not in field_names

    def test_embed_is_discord_embed_instance(self):
        injury = _make_injury()
        embed = build_injury_info_embed(injury)
        assert isinstance(embed, discord.Embed)

    def test_health_impact_underscores_replaced(self):
        injury = _make_injury(health_impact="moderate_negative")
        embed = build_injury_info_embed(injury)
        hi_field = next(f for f in embed.fields if f.name == "Health Impact")
        assert "_" not in hi_field.value
        assert "Moderate negative" in hi_field.value


# ---------------------------------------------------------------------------
# InjuryDropdownControls
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestInjuryDropdownControls:
    def test_empty_injuries_disables_select_and_info(self):
        controls = InjuryDropdownControls(injuries=[])
        assert controls.select.disabled is True
        assert controls.info_button.disabled is True

    def test_with_injuries_select_enabled(self):
        injury = _make_injury(id=1, name="Bruise")
        controls = InjuryDropdownControls(injuries=[InjuryOption(injury=injury, label="Bruise")])
        assert controls.select.disabled is False
        assert controls.info_button.disabled is True

    def test_custom_placeholder(self):
        controls = InjuryDropdownControls(injuries=[], placeholder="Pick an injury")
        assert controls.select.placeholder == "Pick an injury"

    async def test_attach_adds_items(self):
        injury = _make_injury()
        controls = InjuryDropdownControls(injuries=[InjuryOption(injury=injury, label="Test")])
        view = discord.ui.View()
        controls.attach(view, row=0)
        assert len(view.children) >= 2

    def test_severity_sort_order(self):
        injuries = [
            InjuryOption(injury=_make_injury(id=1, name="Critical", severity="critical"), label="Critical"),
            InjuryOption(injury=_make_injury(id=2, name="Trivial", severity="trivial"), label="Trivial"),
            InjuryOption(injury=_make_injury(id=3, name="Moderate", severity="moderate"), label="Moderate"),
        ]
        controls = InjuryDropdownControls(injuries=injuries)
        option_values = [opt.value for opt in controls.select.options]
        # trivial (id=2) should come first
        assert option_values[0] == "2"

    async def test_on_select_enables_info_button(self):
        injury = _make_injury(id=1, name="Fracture")
        controls = InjuryDropdownControls(injuries=[InjuryOption(injury=injury, label="Fracture")])
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
                "src.bot.ui.components.injury_dropdown.edit_interaction",
                new_callable=AsyncMock,
            ),
        ):
            await controls._on_select(interaction)

        assert controls.selected is not None
        assert controls.selected.name == "Fracture"
        assert controls.info_button.disabled is False

    async def test_on_select_none_value_disables_info(self):
        controls = InjuryDropdownControls(injuries=[InjuryOption(injury=_make_injury(), label="Test")])
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
                "src.bot.ui.components.injury_dropdown.edit_interaction",
                new_callable=AsyncMock,
            ),
        ):
            await controls._on_select(interaction)

        assert controls.selected is None
        assert controls.info_button.disabled is True

    async def test_on_info_sends_embed(self):
        injury = _make_injury(id=1, name="Torn Muscle")
        controls = InjuryDropdownControls(injuries=[InjuryOption(injury=injury, label="Torn Muscle")])
        controls.selected = injury

        interaction = MagicMock()

        with patch(
            "src.bot.ui.components.injury_dropdown.reply_to_interacted_message",
            new_callable=AsyncMock,
        ) as mock_reply:
            await controls._on_info(interaction)
            mock_reply.assert_called_once()
            embed_arg = mock_reply.call_args[1]["embed"]
            assert embed_arg.title == "Torn Muscle"

    async def test_on_info_noop_when_no_selection(self):
        controls = InjuryDropdownControls(injuries=[])
        controls.selected = None
        interaction = MagicMock()

        with patch(
            "src.bot.ui.components.injury_dropdown.reply_to_interacted_message",
            new_callable=AsyncMock,
        ) as mock_reply:
            await controls._on_info(interaction)
            mock_reply.assert_not_called()

    async def test_on_select_sets_default_option(self):
        injury = _make_injury(id=1, name="Bruise")
        controls = InjuryDropdownControls(injuries=[InjuryOption(injury=injury, label="Bruise")])
        view = discord.ui.View()
        controls.attach(view, row=0)

        interaction = MagicMock()

        with (
            patch.object(
                type(controls.select),
                "values",
                new_callable=lambda: property(lambda self: ["1"]),
            ),
            patch(
                "src.bot.ui.components.injury_dropdown.edit_interaction",
                new_callable=AsyncMock,
            ),
        ):
            await controls._on_select(interaction)

        selected_opts = [opt for opt in controls.select.options if opt.default]
        assert len(selected_opts) == 1
        assert selected_opts[0].value == "1"
