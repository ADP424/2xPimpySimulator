"""Tests for src/bot/commands/event_history.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestEventHistoryCommand:
    async def test_no_history(self):
        from src.bot.commands import register_event_history_command

        callback = capture_command_callback(register_event_history_command)
        interaction = make_interaction()

        with patch("src.bot.commands.event_history.get_event_history", new_callable=AsyncMock, return_value=[]):
            await callback(interaction, limit=25)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "not" in msg.lower() or "no" in msg.lower()

    async def test_sends_dm_on_success(self):
        from src.bot.commands import register_event_history_command

        callback = capture_command_callback(register_event_history_command)
        interaction = make_interaction()

        with (
            patch(
                "src.bot.commands.event_history.get_event_history",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch("src.bot.commands.event_history.send_event_history_dm", new_callable=AsyncMock, return_value=True),
        ):
            await callback(interaction, limit=25)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "sent" in msg.lower() or "dm" in msg.lower()
