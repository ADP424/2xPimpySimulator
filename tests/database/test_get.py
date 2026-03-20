"""Tests for src/database/get.py.

Each public function opens its own session_scope, so we mock session_scope
to inject a fake session and control query results.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_scope(scalar_result=None, scalars_result=None, tuples_result=None):
    """
    Return an async context-manager mock whose session.execute returns
    controllable results.
    """
    mock_session = AsyncMock()

    # .execute() returns an object with .scalar_one_or_none(), .scalars(), .tuples()
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = scalar_result
    if scalars_result is not None:
        mock_response.scalars.return_value.all.return_value = scalars_result
    if tuples_result is not None:
        mock_response.tuples.return_value.all.return_value = tuples_result

    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.scalar = AsyncMock(return_value=scalar_result)

    # Build an async context manager that yields mock_session
    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _FakeScope, mock_session


# ---------------------------------------------------------------------------
# get_pooch_by_id
# ---------------------------------------------------------------------------


async def test_get_pooch_by_id_returns_pooch():
    """When a pooch exists, the function should return it."""
    fake_pooch = SimpleNamespace(id=1, name="Buddy")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_pooch)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_pooch_by_id

        result = await get_pooch_by_id(1)

    assert result is fake_pooch


async def test_get_pooch_by_id_returns_none():
    """When no pooch exists, the function should return None."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_pooch_by_id

        result = await get_pooch_by_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_owner_by_discord_id
# ---------------------------------------------------------------------------


async def test_get_owner_by_discord_id_returns_owner():
    """When an owner exists, the function should return it."""
    fake_owner = SimpleNamespace(discord_id=123, dollars=100)
    scope_cls, _ = _mock_session_scope(scalar_result=fake_owner)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_owner_by_discord_id

        result = await get_owner_by_discord_id(123)

    assert result is fake_owner


async def test_get_owner_by_discord_id_returns_none_when_missing():
    """When no owner exists, the function should return None."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_owner_by_discord_id

        result = await get_owner_by_discord_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_breed_by_id / get_breed_by_name
# ---------------------------------------------------------------------------


async def test_get_breed_by_id_returns_breed():
    fake_breed = SimpleNamespace(id=5, name="Poodle")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_breed)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_breed_by_id

        result = await get_breed_by_id(5)

    assert result is fake_breed


async def test_get_breed_by_name_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_breed_by_name

        result = await get_breed_by_name("nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# get_mutation_by_id
# ---------------------------------------------------------------------------


async def test_get_mutation_by_id_returns_mutation():
    fake_mutation = SimpleNamespace(id=3, name="Cataracts")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_mutation)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_mutation_by_id

        result = await get_mutation_by_id(3)

    assert result is fake_mutation


# ---------------------------------------------------------------------------
# get_kennel_by_id
# ---------------------------------------------------------------------------


async def test_get_kennel_by_id_returns_kennel():
    fake_kennel = SimpleNamespace(id=10, name="Main Kennel")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_kennel)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_kennel_by_id

        result = await get_kennel_by_id(10)

    assert result is fake_kennel


async def test_get_kennel_by_id_returns_none():
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_kennel_by_id

        result = await get_kennel_by_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_random_breed_ids
# ---------------------------------------------------------------------------


async def test_get_random_breed_ids_returns_empty_for_zero():
    """Requesting 0 breed IDs should return an empty list without hitting the DB."""
    from src.database.get import get_random_breed_ids

    result = await get_random_breed_ids(0)
    assert result == []


async def test_get_random_breed_ids_returns_empty_for_negative():
    """Requesting negative breed IDs should return an empty list."""
    from src.database.get import get_random_breed_ids

    result = await get_random_breed_ids(-1)
    assert result == []


# ---------------------------------------------------------------------------
# get_vendor_by_id
# ---------------------------------------------------------------------------


async def test_get_vendor_by_id_returns_vendor():
    fake_vendor = SimpleNamespace(id=7, name="Bob")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_vendor)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_vendor_by_id

        result = await get_vendor_by_id(7)

    assert result is fake_vendor


# ---------------------------------------------------------------------------
# get_pooch_virginity_status
# ---------------------------------------------------------------------------


async def test_get_pooch_virginity_status_returns_bool():
    scope_cls, _ = _mock_session_scope(scalar_result=True)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_pooch_virginity_status

        result = await get_pooch_virginity_status(1)

    assert result is True


async def test_get_pooch_virginity_status_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database.get import get_pooch_virginity_status

        result = await get_pooch_virginity_status(999)

    assert result is None
