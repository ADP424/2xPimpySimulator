"""Tests for src/bot/commands/server_event.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestServerEventCommand:
    async def test_requires_guild(self):
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()
        interaction.guild_id = None

        await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    async def test_no_active_event(self):
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()

        with patch("src.bot.commands.server_event.get_active_server_event", new_callable=AsyncMock, return_value=None):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "no active" in msg.lower()

    async def test_shows_active_event(self):
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()

        mock_event = MagicMock()
        mock_event.occurrence_id = 1
        mock_event.server_discord_id = 200

        with (
            patch(
                "src.bot.commands.server_event.get_active_server_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.bot.commands.server_event.build_server_event_embed",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
        ):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        kwargs = interaction.response.send_message.call_args[1]
        assert "embed" in kwargs
        assert "view" in kwargs
