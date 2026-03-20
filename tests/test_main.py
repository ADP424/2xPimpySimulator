"""Contract tests for main.py CLI dispatch logic."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest


def _run_main_with_args(args: list[str], mock_modules: dict):
    """Run main.py with the given CLI args and pre-loaded mock modules.

    We inject fake 'src.web', 'src.bot', 'src.database' modules into sys.modules
    before runpy.run_path so that the top-level imports in main.py resolve to our mocks.
    """
    import runpy

    # Build fake sub-modules
    fake_src = ModuleType("src")
    fake_web = ModuleType("src.web")
    fake_bot = ModuleType("src.bot")
    fake_db = ModuleType("src.database")

    fake_web.run = mock_modules["run_web"]
    fake_bot.run = mock_modules["run_bot"]
    fake_db.reset_database = mock_modules["reset_database"]
    fake_db.load_resources = mock_modules["load_resources"]

    fake_src.web = fake_web
    fake_src.bot = fake_bot
    fake_src.database = fake_db

    saved_modules = {}
    inject = {
        "src": fake_src,
        "src.web": fake_web,
        "src.web.run": fake_web,
        "src.bot": fake_bot,
        "src.bot.app": fake_bot,
        "src.database": fake_db,
        "src.database.load": fake_db,
    }

    for name, mod in inject.items():
        saved_modules[name] = sys.modules.get(name)
        sys.modules[name] = mod

    saved_argv = sys.argv
    try:
        sys.argv = ["main.py"] + args
        runpy.run_path("main.py", run_name="__main__")
    finally:
        sys.argv = saved_argv
        for name in inject:
            if saved_modules[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved_modules[name]


@pytest.mark.contract
def test_web_app_flag():
    """The -w flag should call run_web_app and nothing else."""
    mocks = {
        "run_web": MagicMock(),
        "run_bot": MagicMock(),
        "reset_database": MagicMock(),
        "load_resources": AsyncMock(),
    }
    _run_main_with_args(["-w"], mocks)

    mocks["run_web"].assert_called_once()
    mocks["run_bot"].assert_not_called()
    mocks["reset_database"].assert_not_called()


@pytest.mark.contract
def test_reset_db_flag():
    """The -r flag should call reset_database then load_resources."""
    mocks = {
        "run_web": MagicMock(),
        "run_bot": MagicMock(),
        "reset_database": MagicMock(),
        "load_resources": AsyncMock(),
    }
    _run_main_with_args(["-r"], mocks)

    mocks["reset_database"].assert_called_once()
    mocks["load_resources"].assert_called_once()
    mocks["run_web"].assert_not_called()
    mocks["run_bot"].assert_not_called()


@pytest.mark.contract
def test_update_names_flag():
    """The -n flag should call run_bot(update_names_only=True)."""
    mocks = {
        "run_web": MagicMock(),
        "run_bot": MagicMock(),
        "reset_database": MagicMock(),
        "load_resources": AsyncMock(),
    }
    _run_main_with_args(["-n"], mocks)

    mocks["run_bot"].assert_called_once_with(update_names_only=True)
    mocks["run_web"].assert_not_called()
    mocks["reset_database"].assert_not_called()


@pytest.mark.contract
def test_default_runs_bot():
    """No flags should call run_bot(skip_startup_day_change=False)."""
    mocks = {
        "run_web": MagicMock(),
        "run_bot": MagicMock(),
        "reset_database": MagicMock(),
        "load_resources": AsyncMock(),
    }
    _run_main_with_args([], mocks)

    mocks["run_bot"].assert_called_once_with(skip_startup_day_change=False)
    mocks["run_web"].assert_not_called()
    mocks["reset_database"].assert_not_called()


@pytest.mark.contract
def test_skip_startup_day_change_flag():
    """The -s flag should call run_bot(skip_startup_day_change=True)."""
    mocks = {
        "run_web": MagicMock(),
        "run_bot": MagicMock(),
        "reset_database": MagicMock(),
        "load_resources": AsyncMock(),
    }
    _run_main_with_args(["-s"], mocks)

    mocks["run_bot"].assert_called_once_with(skip_startup_day_change=True)
    mocks["run_web"].assert_not_called()
    mocks["reset_database"].assert_not_called()
