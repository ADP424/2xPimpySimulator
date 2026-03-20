"""Tests for src/database/delete.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_scope(entity=None):
    """
    Return a mock session_scope yielding a session whose .execute()
    returns `entity` via .scalar_one_or_none().
    """
    mock_session = AsyncMock()

    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = entity
    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.get = AsyncMock(return_value=entity)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _FakeScope, mock_session


# ---------------------------------------------------------------------------
# delete_pooch
# ---------------------------------------------------------------------------


async def test_delete_pooch_returns_deleted_pooch():
    """delete_pooch should return the deleted pooch."""
    fake_pooch = SimpleNamespace(id=1, name="Buddy")
    scope_cls, mock_session = _mock_session_scope(entity=fake_pooch)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import delete_pooch

        result = await delete_pooch(1)

    assert result is fake_pooch
    # Verify the delete query was executed
    assert mock_session.execute.await_count >= 1


async def test_delete_pooch_returns_none_when_missing():
    """delete_pooch should return None when the pooch doesn't exist."""
    scope_cls, _ = _mock_session_scope(entity=None)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import delete_pooch

        result = await delete_pooch(999)

    assert result is None


# ---------------------------------------------------------------------------
# remove_pooch_from_kennel
# ---------------------------------------------------------------------------


async def test_remove_pooch_from_kennel_returns_pooch():
    """remove_pooch_from_kennel should return the pooch after removing it."""
    fake_pooch = SimpleNamespace(id=1, name="Buddy")
    scope_cls, mock_session = _mock_session_scope(entity=fake_pooch)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_pooch_from_kennel

        result = await remove_pooch_from_kennel(1)

    assert result is fake_pooch


async def test_remove_pooch_from_kennel_returns_none_when_not_in_kennel():
    """remove_pooch_from_kennel should return None when pooch isn't in a kennel."""
    scope_cls, _ = _mock_session_scope(entity=None)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_pooch_from_kennel

        result = await remove_pooch_from_kennel(999)

    assert result is None


# ---------------------------------------------------------------------------
# remove_mutation_from_pooch
# ---------------------------------------------------------------------------


async def test_remove_mutation_from_pooch_returns_removed():
    """remove_mutation_from_pooch should delete and return the relationship."""
    fake_pm = SimpleNamespace(pooch_id=1, mutation_id=2)
    scope_cls, mock_session = _mock_session_scope(entity=fake_pm)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_mutation_from_pooch

        result = await remove_mutation_from_pooch(1, 2)

    assert result is fake_pm
    mock_session.delete.assert_awaited_once_with(fake_pm)


async def test_remove_mutation_from_pooch_returns_none_when_not_present():
    """remove_mutation_from_pooch should return None when the mutation isn't on the pooch."""
    scope_cls, mock_session = _mock_session_scope(entity=None)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_mutation_from_pooch

        result = await remove_mutation_from_pooch(1, 999)

    assert result is None
    mock_session.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# delete_pregnancy
# ---------------------------------------------------------------------------


async def test_delete_pregnancy_returns_fetus():
    """delete_pregnancy should return the fetus pooch and delete the relationship."""
    fake_fetus = SimpleNamespace(id=20, name="Baby")
    scope_cls, mock_session = _mock_session_scope(entity=fake_fetus)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import delete_pregnancy

        result = await delete_pregnancy(mother_id=10, fetus_id=20)

    assert result is fake_fetus


async def test_delete_pregnancy_returns_none_when_fetus_missing():
    scope_cls, _ = _mock_session_scope(entity=None)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import delete_pregnancy

        result = await delete_pregnancy(mother_id=10, fetus_id=999)

    assert result is None


# ---------------------------------------------------------------------------
# clear_vendor_pooch_stock
# ---------------------------------------------------------------------------


async def test_clear_vendor_pooch_stock_returns_vendor():
    fake_vendor = SimpleNamespace(id=1, name="Bob")
    scope_cls, mock_session = _mock_session_scope(entity=fake_vendor)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import clear_vendor_pooch_stock

        result = await clear_vendor_pooch_stock(1)

    assert result is fake_vendor


async def test_clear_vendor_pooch_stock_returns_none_when_vendor_missing():
    scope_cls, _ = _mock_session_scope(entity=None)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import clear_vendor_pooch_stock

        result = await clear_vendor_pooch_stock(999)

    assert result is None


# ---------------------------------------------------------------------------
# remove_pooch_from_strays
# ---------------------------------------------------------------------------


async def test_remove_pooch_from_strays_returns_stray():
    fake_stray = SimpleNamespace(pooch_id=5, server_discord_id=111)
    scope_cls, mock_session = _mock_session_scope(entity=fake_stray)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_pooch_from_strays

        result = await remove_pooch_from_strays(5)

    assert result is fake_stray
    mock_session.delete.assert_awaited_once()


async def test_remove_pooch_from_strays_returns_none_when_not_stray():
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.delete.session_scope", return_value=_FakeScope()):
        from src.database.delete import remove_pooch_from_strays

        result = await remove_pooch_from_strays(999)

    assert result is None


# ---------------------------------------------------------------------------
# remove_breed_from_pooch
# ---------------------------------------------------------------------------


async def test_remove_breed_from_pooch_returns_removed():
    fake_row = SimpleNamespace(pooch_id=1, breed_id=3)
    scope_cls, mock_session = _mock_session_scope(entity=fake_row)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_breed_from_pooch

        result = await remove_breed_from_pooch(1, 3)

    assert result is fake_row
    mock_session.delete.assert_awaited_once()


async def test_remove_breed_from_pooch_returns_none():
    scope_cls, mock_session = _mock_session_scope(entity=None)

    with patch("src.database.delete.session_scope", return_value=scope_cls()):
        from src.database.delete import remove_breed_from_pooch

        result = await remove_breed_from_pooch(1, 999)

    assert result is None
