"""Tests for src/bot/commands/get_money.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestGetMoneyCommand:
    async def test_requires_guild(self):
        from src.bot.commands import register_get_money_command

        callback = capture_command_callback(register_get_money_command)
        interaction = make_interaction()
        interaction.guild_id = None

        await callback(interaction, amount=100)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    async def test_adds_money_and_responds(self):
        from src.bot.commands import register_get_money_command

        callback = capture_command_callback(register_get_money_command)
        interaction = make_interaction()
        mock_owner = MagicMock()
        mock_owner.dollars = 150

        with patch("src.bot.commands.get_money.add_money", new_callable=AsyncMock, return_value=mock_owner):
            await callback(interaction, amount=50)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "$50" in msg
        assert "$150" in msg
