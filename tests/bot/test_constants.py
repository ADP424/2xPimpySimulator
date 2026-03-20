"""Tests for src/bot/constants.py."""


def test_view_timeout_is_positive():
    from src.bot.constants import VIEW_TIMEOUT

    assert VIEW_TIMEOUT > 0


def test_event_loop_interval_is_positive():
    from src.bot.constants import EVENT_LOOP_INTERVAL_SECONDS

    assert EVENT_LOOP_INTERVAL_SECONDS > 0


def test_items_per_page_is_positive():
    from src.bot.constants import ITEMS_PER_PAGE

    assert ITEMS_PER_PAGE > 0


def test_max_name_length_is_positive():
    from src.bot.constants import MAX_NAME_LENGTH

    assert MAX_NAME_LENGTH > 0


def test_guilds_is_non_empty_list():
    from src.bot.constants import GUILDS

    assert isinstance(GUILDS, list)
    assert len(GUILDS) > 0
