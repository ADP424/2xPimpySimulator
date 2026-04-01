"""Contract tests for src/bot/app.py."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.contract
def test_missing_token_raises():
    """run() should raise RuntimeError when DISCORD_TOKEN is not set."""
    with (
        patch("src.bot.app.load_dotenv"),
        patch.dict("os.environ", {"DISCORD_TOKEN": ""}, clear=False),
        patch("src.bot.app.os.getenv", side_effect=lambda k, d=None: {"STAGE": "dev", "TZ": "UTC"}.get(k, d)),
    ):
        from src.bot import run

        with pytest.raises(RuntimeError, match="DISCORD_TOKEN not set"):
            run()


@pytest.mark.contract
def test_dev_stage_registers_dev_commands():
    """In dev stage, dev-only commands are registered and synced to guilds."""
    fake_bot = MagicMock()
    fake_bot.run = MagicMock()
    fake_tree = MagicMock()

    with (
        patch("src.bot.app.load_dotenv"),
        patch(
            "src.bot.app.os.getenv",
            side_effect=lambda k, d=None: {"DISCORD_TOKEN": "test-token", "STAGE": "dev", "TZ": "UTC"}.get(k, d),
        ),
        patch("src.bot.app.discord.Client", return_value=fake_bot),
        patch("src.bot.app.app_commands.CommandTree", return_value=fake_tree),
        patch("src.bot.app.register_home_command") as mock_home,
        patch("src.bot.app.register_town_command") as mock_town,
        patch("src.bot.app.register_set_event_channel_command") as mock_set_channel,
        patch("src.bot.app.register_event_history_command"),
        patch("src.bot.app.register_pending_events_command"),
        patch("src.bot.app.register_server_event_command"),
        patch("src.bot.app.register_get_money_command") as mock_get_money,
        patch("src.bot.app.register_pause_day_loop_command") as mock_pause,
        patch("src.bot.app.register_increment_day_command") as mock_inc_day,
        patch("src.bot.app.register_trigger_event_command") as mock_trigger,
    ):
        from src.bot import run

        run()

        # Core commands always registered
        mock_home.assert_called_once_with(fake_tree)
        mock_town.assert_called_once_with(fake_tree)
        mock_set_channel.assert_called_once_with(fake_tree)

        # Dev-only commands registered in dev stage
        mock_get_money.assert_called_once_with(fake_tree)
        mock_pause.assert_called_once_with(fake_tree)
        mock_inc_day.assert_called_once_with(fake_tree)
        mock_trigger.assert_called_once_with(fake_tree)

        fake_bot.run.assert_called_once_with("test-token")


@pytest.mark.contract
def test_prod_stage_does_not_register_dev_commands():
    """In prod stage, dev-only commands are NOT registered."""
    fake_bot = MagicMock()
    fake_bot.run = MagicMock()
    fake_tree = MagicMock()

    with (
        patch("src.bot.app.load_dotenv"),
        patch(
            "src.bot.app.os.getenv",
            side_effect=lambda k, d=None: {"DISCORD_TOKEN": "test-token", "STAGE": "prod", "TZ": "UTC"}.get(k, d),
        ),
        patch("src.bot.app.discord.Client", return_value=fake_bot),
        patch("src.bot.app.app_commands.CommandTree", return_value=fake_tree),
        patch("src.bot.app.register_home_command"),
        patch("src.bot.app.register_town_command"),
        patch("src.bot.app.register_set_event_channel_command"),
        patch("src.bot.app.register_event_history_command"),
        patch("src.bot.app.register_pending_events_command"),
        patch("src.bot.app.register_server_event_command"),
        patch("src.bot.app.register_get_money_command") as mock_get_money,
        patch("src.bot.app.register_pause_day_loop_command") as mock_pause,
        patch("src.bot.app.register_increment_day_command") as mock_inc_day,
        patch("src.bot.app.register_trigger_event_command") as mock_trigger,
    ):
        from src.bot import run

        run()

        # Dev-only commands should NOT be registered
        mock_get_money.assert_not_called()
        mock_pause.assert_not_called()
        mock_inc_day.assert_not_called()
        mock_trigger.assert_not_called()
