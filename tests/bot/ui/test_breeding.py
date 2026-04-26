"""Contract tests for src/bot/ui/breeding.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.breeding import BreedMateView


def _make_pooch(id=1, name="Rex", sex="male"):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    pooch.sex = sex
    return pooch


@pytest.mark.contract
class TestBreedMateView:
    async def test_creates_view_with_mates(self):
        pooch = _make_pooch(id=1, name="Mama", sex="female")
        mates = [_make_pooch(id=2, name="Papa", sex="male")]
        view = BreedMateView(pooch=pooch, mates=mates)
        assert isinstance(view, discord.ui.View)
        assert len(view.children) >= 1

    async def test_select_placeholder_includes_pooch_name(self):
        pooch = _make_pooch(id=1, name="Bella", sex="female")
        mates = [_make_pooch(id=2, name="Max", sex="male")]
        view = BreedMateView(pooch=pooch, mates=mates)
        assert "Bella" in view.select.placeholder

    async def test_select_options_match_mates(self):
        pooch = _make_pooch(id=1, name="Mama", sex="female")
        mates = [
            _make_pooch(id=2, name="Alpha", sex="male"),
            _make_pooch(id=3, name="Bravo", sex="male"),
        ]
        view = BreedMateView(pooch=pooch, mates=mates)
        option_labels = [opt.label for opt in view.select.options]
        assert "Alpha" in option_labels
        assert "Bravo" in option_labels

    async def test_select_breeds_pooches(self):
        pooch = _make_pooch(id=1, name="Mama", sex="female")
        mate = _make_pooch(id=2, name="Papa", sex="male")
        view = BreedMateView(pooch=pooch, mates=[mate])

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.response.edit_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None
        interaction.channel = MagicMock()
        interaction.channel.send = AsyncMock()

        mock_puppies = [MagicMock()]
        with (
            patch.object(type(view.select), "values", new_callable=lambda: property(lambda self: ["2"])),
            patch("src.bot.ui.breeding.breed_pooches", new_callable=AsyncMock, return_value=mock_puppies),
            patch("src.bot.ui.breeding.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_select(interaction)

            mock_r.reply.assert_called_once()
            msg = mock_r.reply.call_args[1]["content"]
            assert "1" in msg and "puppy" in msg.lower()

    async def test_select_handles_breeding_error(self):
        pooch = _make_pooch(id=1, name="Mama", sex="female")
        mate = _make_pooch(id=2, name="Papa", sex="male")
        view = BreedMateView(pooch=pooch, mates=[mate])

        interaction = MagicMock()

        with (
            patch.object(type(view.select), "values", new_callable=lambda: property(lambda self: ["2"])),
            patch("src.bot.ui.breeding.breed_pooches", new_callable=AsyncMock, side_effect=ValueError("Too young!")),
            patch("src.bot.ui.breeding.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_select(interaction)

            mock_r.reply.assert_called_once()
            msg = mock_r.reply.call_args[1]["content"]
            assert "Too young!" in msg

    async def test_twins_message(self):
        pooch = _make_pooch(id=1, name="Mama", sex="female")
        mate = _make_pooch(id=2, name="Papa", sex="male")
        view = BreedMateView(pooch=pooch, mates=[mate])

        interaction = MagicMock()

        mock_puppies = [MagicMock(), MagicMock()]
        with (
            patch.object(type(view.select), "values", new_callable=lambda: property(lambda self: ["2"])),
            patch("src.bot.ui.breeding.breed_pooches", new_callable=AsyncMock, return_value=mock_puppies),
            patch("src.bot.ui.breeding.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_select(interaction)

            msg = mock_r.reply.call_args[1]["content"]
            assert "Twins" in msg or "2" in msg
