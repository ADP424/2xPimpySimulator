"""Contract tests for src/bot/ui/components/breed_dropdown.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.components import (
    BreedDropdownControls,
    BreedOption,
    build_breed_info_embed,
)


def _make_breed(
    id=1,
    name="Golden Retriever",
    alt_name="Goldie",
    category="retriever",
    description="A good boy.",
    rarity="common",
    min_size=50,
    max_size=70,
    parameters=None,
):
    from src.game.models.breed import Breed

    return Breed(
        id=id,
        name=name,
        alt_name=alt_name,
        category=category,
        description=description,
        rarity=rarity,
        min_size=min_size,
        max_size=max_size,
        parameters=parameters or {},
    )


@pytest.mark.contract
class TestBuildBreedInfoEmbed:
    def test_basic_embed(self):
        breed = _make_breed()
        embed = build_breed_info_embed(breed)
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Golden Retriever"
        assert "A good boy." in embed.description

    def test_embed_fields(self):
        breed = _make_breed(alt_name="Goldie", rarity="rare")
        embed = build_breed_info_embed(breed)
        field_names = [f.name for f in embed.fields]
        assert "Also Known As" in field_names
        assert "Category" in field_names
        assert "Rarity" in field_names

    def test_no_alt_name_shows_dash(self):
        breed = _make_breed(alt_name="")
        embed = build_breed_info_embed(breed)
        also_known = next(f for f in embed.fields if f.name == "Also Known As")
        assert also_known.value == "\u2014"

    def test_size_range(self):
        embed = build_breed_info_embed(_make_breed(min_size=3, max_size=5))
        assert next(f for f in embed.fields if f.name == "Size").value == "3–5"

    def test_fixed_size(self):
        embed = build_breed_info_embed(_make_breed(min_size=4, max_size=4))
        assert next(f for f in embed.fields if f.name == "Size").value == "4"

    def test_stat_effects(self):
        embed = build_breed_info_embed(_make_breed(parameters={"intelligence_add": 8, "cuteness_mult": 0.33}))
        stat_effects = next(f for f in embed.fields if f.name == "Stat Effects")
        assert stat_effects.value == "▼ Cuteness ×0.33\n▲ Intelligence +8"

    def test_no_stat_effects(self):
        embed = build_breed_info_embed(_make_breed())
        assert next(f for f in embed.fields if f.name == "Stat Effects").value == "None"


@pytest.mark.contract
class TestBreedDropdownControls:
    def test_empty_breeds(self):
        controls = BreedDropdownControls(breeds=[])
        assert controls.select.disabled is True
        assert controls.info_button.disabled is True

    def test_with_breeds(self):
        breed = _make_breed(id=1, name="Lab")
        controls = BreedDropdownControls(breeds=[BreedOption(breed=breed, label="Lab")])
        assert controls.select.disabled is False
        assert controls.info_button.disabled is True  # disabled until selection

    async def test_attach_adds_items(self):
        breed = _make_breed(id=1, name="Pug")
        controls = BreedDropdownControls(breeds=[BreedOption(breed=breed, label="Pug")])
        view = discord.ui.View()
        controls.attach(view, row=0)
        assert len(view.children) >= 2  # select + button

    async def test_select_callback_enables_info(self):
        breed = _make_breed(id=1, name="Pug")
        controls = BreedDropdownControls(breeds=[BreedOption(breed=breed, label="Pug")])
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
            patch("src.bot.ui.components.breed_dropdown.edit_interaction", new_callable=AsyncMock),
        ):
            await controls._on_select(interaction)

        assert controls.selected is not None
        assert controls.selected.name == "Pug"
        assert controls.info_button.disabled is False

    async def test_select_none_disables_info(self):
        controls = BreedDropdownControls(breeds=[])

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.edit_message = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["__none__"])),
            patch("src.bot.ui.components.breed_dropdown.edit_interaction", new_callable=AsyncMock),
        ):
            await controls._on_select(interaction)

        assert controls.selected is None
        assert controls.info_button.disabled is True

    async def test_info_button_sends_embed(self):
        breed = _make_breed(id=1, name="Beagle")
        controls = BreedDropdownControls(breeds=[BreedOption(breed=breed, label="Beagle")])
        controls.selected = breed

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None
        interaction.channel = MagicMock()
        interaction.channel.send = AsyncMock()

        with patch(
            "src.bot.ui.components.breed_dropdown.reply_to_interacted_message", new_callable=AsyncMock
        ) as mock_reply:
            await controls._on_info(interaction)
            mock_reply.assert_called_once()
            embed_arg = mock_reply.call_args[1]["embed"]
            assert embed_arg.title == "Beagle"
