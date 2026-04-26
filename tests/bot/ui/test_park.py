"""Contract tests for src/bot/ui/park.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.park import ParkView


@pytest.mark.contract
class TestParkView:
    async def test_creates_view(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_attract_stray_button(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Attract a Stray" for b in buttons)

    async def test_has_use_bone_button(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Use a Bone" for b in buttons)

    async def test_has_town_button(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Town" for b in buttons)

    async def test_interaction_check_owner_only(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False


@pytest.mark.contract
class TestAttractStrayButton:
    async def test_defers_and_calls_visit_park(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        attract_button = next(
            c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Attract a Stray"
        )

        interaction = MagicMock()

        with (
            patch("src.bot.ui.park.visit_park", new_callable=AsyncMock, return_value=(True, "You caught a stray!")),
            patch("src.bot.ui.park.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await attract_button.callback(interaction)

            mock_r.defer.assert_called_once_with(thinking=True)
            mock_r.reply.assert_called_once()

    async def test_handles_exception(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        attract_button = next(
            c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Attract a Stray"
        )

        interaction = MagicMock()

        with (
            patch("src.bot.ui.park.visit_park", new_callable=AsyncMock, side_effect=Exception("Park error")),
            patch("src.bot.ui.park.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r

            await attract_button.callback(interaction)
            mock_r.finish_with_error.assert_called_once()


@pytest.mark.contract
class TestUseBoneButton:
    async def test_calls_spend_bone(self):
        view = ParkView(server_discord_id=200, owner_discord_id=100)
        bone_button = next(c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Use a Bone")

        interaction = MagicMock()

        with (
            patch("src.bot.ui.park.spend_bone_at_park", new_callable=AsyncMock, return_value=(False, "No bones left.")),
            patch("src.bot.ui.park.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await bone_button.callback(interaction)

            mock_r.defer.assert_called_once_with(thinking=True)
            mock_r.reply.assert_called_once()
