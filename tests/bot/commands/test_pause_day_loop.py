"""Tests for src/bot/commands/pause_day_loop.py."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestPauseDayLoopCommand:
    async def test_toggles_pause(self):
        from src.bot.commands import register_pause_day_loop_command

        callback = capture_command_callback(register_pause_day_loop_command)
        interaction = make_interaction()

        with (
            patch("src.bot.commands.pause_day_loop.is_day_change_paused", return_value=False),
            patch("src.bot.commands.pause_day_loop.set_day_change_paused", new_callable=AsyncMock) as mock_set,
        ):
            await callback(interaction)
            mock_set.assert_called_once_with(interaction.client, paused=True)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "paused" in msg.lower()
