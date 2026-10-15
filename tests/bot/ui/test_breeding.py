"""Contract tests for src/bot/ui/breeding.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.breeding import BreedMateView
from src.game import BreedingOutcome


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
        view = BreedMateView(pooch=pooch, mates=mates, chance=0.5)
        assert isinstance(view, discord.ui.View)
        assert len(view.children) >= 1

    async def test_select_placeholder_includes_pooch_name(self):
        pooch = _make_pooch(id=1, name="Bella", sex="female")
        mates = [_make_pooch(id=2, name="Max", sex="male")]
        view = BreedMateView(pooch=pooch, mates=mates, chance=0.5)
        assert "Bella" in view.select.placeholder

    async def test_select_options_match_mates(self):
        pooch = _make_pooch(id=1, name="Mama", sex="female")
        mates = [
            _make_pooch(id=2, name="Alpha", sex="male"),
            _make_pooch(id=3, name="Bravo", sex="male"),
        ]
        view = BreedMateView(pooch=pooch, mates=mates, chance=0.5)
        option_labels = [opt.label for opt in view.select.options]
        assert "Alpha" in option_labels
        assert "Bravo" in option_labels

    async def _select(self, view, outcome=None, error=None, user_id=7):
        interaction = MagicMock()
        interaction.user.id = user_id
        breed = AsyncMock(return_value=outcome, side_effect=error)
        with (
            patch.object(type(view.select), "values", new_callable=lambda: property(lambda self: ["2"])),
            patch("src.bot.ui.breeding.breed_with_mate_choice", new=breed),
            patch("src.bot.ui.breeding.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_select(interaction)
        return mock_r, breed

    def _outcome(self, puppies=1, disease_events=(), distracted=False):
        male = _make_pooch(id=2, name="Papa", sex="male")
        intended = _make_pooch(id=1, name="Mama", sex="female")
        female = _make_pooch(id=3, name="Bruno's Gal", sex="female") if distracted else intended
        return BreedingOutcome(list(range(puppies)), list(disease_events), male, female, intended)

    async def test_select_breeds_pooches_as_clicking_user(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        mock_r, breed = await self._select(view, outcome=self._outcome())

        breed.assert_awaited_once_with(7, 1, 2)
        msg = mock_r.reply.call_args[1]["content"]
        assert msg == "✅ **Breeding successful.** Papa and Mama are expecting **1** puppy."

    async def test_select_handles_breeding_error(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        mock_r, _ = await self._select(view, error=ValueError("Too young!"))

        mock_r.reply.assert_called_once()
        assert mock_r.reply.call_args[1]["content"] == "Too young!"

    async def test_twins_message(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        mock_r, _ = await self._select(view, outcome=self._outcome(puppies=2))
        assert "Twins" in mock_r.reply.call_args[1]["content"]

    async def test_mate_distraction_notification(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        mock_r, _ = await self._select(view, outcome=self._outcome(distracted=True))

        msg = mock_r.reply.call_args[1]["content"]
        assert msg.startswith("💫 ✅ **Papa got distracted**")
        assert "Bruno's Gal" in msg

    async def test_no_distraction_when_same_mate(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        mock_r, _ = await self._select(view, outcome=self._outcome())
        assert "distracted" not in mock_r.reply.call_args[1]["content"].lower()

    async def test_disease_events_appended_as_bullets(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        events = [(1, "Kennel Cough", "spread"), (50, "Parvovirus", "inherited")]
        mock_r, _ = await self._select(view, outcome=self._outcome(disease_events=events))

        msg = mock_r.reply.call_args[1]["content"]
        assert "\n• Mama was exposed to Kennel Cough." in msg
        assert "\n• A puppy inherited Parvovirus." in msg

    async def test_disease_events_empty_no_extra_lines(self):
        view = BreedMateView(pooch=_make_pooch(id=1, name="Mama", sex="female"), mates=[_make_pooch(id=2)], chance=0.5)
        mock_r, _ = await self._select(view, outcome=self._outcome())
        assert "\n" not in mock_r.reply.call_args[1]["content"]
