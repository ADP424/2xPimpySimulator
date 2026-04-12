"""Tests for src/bot/commands/town.py."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestTownCommand:
    async def test_town_requires_guild(self):
        from src.bot.commands import register_town_command

        callback = capture_command_callback(register_town_command)
        interaction = make_interaction()
        interaction.guild_id = None
        interaction.channel_id = None

        await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    @patch("src.bot.commands.town.get_season", new_callable=AsyncMock, return_value="spring")
    async def test_town_sends_view(self, mock_season):
        from src.bot.commands import register_town_command

        callback = capture_command_callback(register_town_command)
        interaction = make_interaction()

        await callback(interaction)

        interaction.response.send_message.assert_called_once()
        kwargs = interaction.response.send_message.call_args[1]
        assert "view" in kwargs
