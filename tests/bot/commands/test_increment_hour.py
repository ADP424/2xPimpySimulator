"""Tests for src/bot/commands/increment_hour.py."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestIncrementHourCommand:
    async def test_queues_hour_change(self):
        from src.bot.commands import register_increment_hour_command

        callback = capture_command_callback(register_increment_hour_command)
        interaction = make_interaction()

        with patch(
            "src.bot.commands.increment_hour.trigger_manual_hour_change", new_callable=AsyncMock
        ) as mock_trigger:
            await callback(interaction)
            mock_trigger.assert_called_once_with(interaction.client)

        interaction.response.send_message.assert_called_once()
