"""Tests for src/database/session.py."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _get_database_url
# ---------------------------------------------------------------------------


def test_get_database_url_constructs_correct_url():
    """_get_database_url should build a postgresql+asyncpg URL from env vars."""
    env = {
        "DATABASE": "testdb",
        "DB_USER": "user",
        "DB_HOST": "localhost",
        "DB_PASSWORD": "pass",
        "DB_PORT": "5432",
    }
    with patch.dict("os.environ", env, clear=False):
        # Re-import so dotenv/environ reads our patched values
        import src.database.session as mod

        importlib.reload(mod)
        url = mod._get_database_url()

    assert url.startswith("postgresql+asyncpg://")
    assert "user" in url
    assert "pass" in url
    assert "localhost" in url
    assert "5432" in url
    assert "testdb" in url


def test_get_database_url_uses_default_port():
    """When DB_PORT is absent the default '5432' should be used."""
    env = {
        "DATABASE": "mydb",
        "DB_USER": "u",
        "DB_HOST": "h",
        "DB_PASSWORD": "p",
    }
    with patch.dict("os.environ", env, clear=True):
        import src.database.session as mod

        importlib.reload(mod)
        url = mod._get_database_url()

    assert "5432" in url


def test_get_database_url_missing_vars_raises():
    """Missing required env vars should raise RuntimeError."""
    import src.database.session as mod

    with patch.object(mod, "load_dotenv"), patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="Missing required env var"):
            mod._get_database_url()


def test_get_database_url_missing_partial_vars_raises():
    """Even with some vars present, missing others should raise."""
    import src.database.session as mod

    env = {"DATABASE": "testdb"}
    with patch.object(mod, "load_dotenv"), patch.dict("os.environ", env, clear=True):
        with pytest.raises(RuntimeError, match="DB_USER"):
            mod._get_database_url()


def test_get_database_url_special_characters_are_quoted():
    """Password and username with special chars should be URL-encoded."""
    env = {
        "DATABASE": "db",
        "DB_USER": "user@host",
        "DB_HOST": "localhost",
        "DB_PASSWORD": "p@ss/word",
        "DB_PORT": "5432",
    }
    with patch.dict("os.environ", env, clear=False):
        import src.database.session as mod

        importlib.reload(mod)
        url = mod._get_database_url()

    # The raw '@' in user/password should be percent-encoded
    assert "user%40host" in url
    assert "p%40ss%2Fword" in url


# ---------------------------------------------------------------------------
# session_scope
# ---------------------------------------------------------------------------


async def test_session_scope_commits_on_success():
    """session_scope should call commit when the block succeeds."""
    mock_session = AsyncMock()

    mock_sessionmaker = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_sessionmaker.return_value = mock_ctx

    with patch("src.database.session._get_sessionmaker", return_value=mock_sessionmaker):
        from src.database import session_scope

        async with session_scope():
            pass  # simulate success

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


async def test_session_scope_rolls_back_on_error():
    """session_scope should call rollback and re-raise when an error occurs."""
    mock_session = AsyncMock()

    mock_sessionmaker = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_sessionmaker.return_value = mock_ctx

    with patch("src.database.session._get_sessionmaker", return_value=mock_sessionmaker):
        from src.database import session_scope

        with pytest.raises(ValueError, match="boom"):
            async with session_scope():
                raise ValueError("boom")

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
