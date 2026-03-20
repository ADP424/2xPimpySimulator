"""Tests for src/database/set.py (creation functions).

Functions under test open their own session_scope, so we mock it.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_scope():
    """Return a mock session that tracks .add() and .flush() calls."""
    mock_session = AsyncMock()
    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.scalar = AsyncMock()
    mock_session._added = added_objects

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _FakeScope, mock_session


# ---------------------------------------------------------------------------
# create_owner
# ---------------------------------------------------------------------------


async def test_create_owner_adds_owner_to_session():
    """create_owner should add an Owner with the given discord_id to the session."""
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_owner

        result = await create_owner(12345)

    assert result.discord_id == 12345
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


async def test_create_server_adds_server_to_session():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_server

        result = await create_server(67890)

    assert result.discord_id == 67890
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_kennel
# ---------------------------------------------------------------------------


async def test_create_kennel_returns_none_when_owner_missing():
    """create_kennel should return None when the owner doesn't exist."""
    with patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)):
        from src.database.set import create_kennel

        result = await create_kennel(999)

    assert result is None


async def test_create_kennel_creates_with_defaults():
    """create_kennel should create a kennel with default name and pooch_limit."""
    fake_owner = SimpleNamespace(discord_id=123)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_kennel

        result = await create_kennel(123)

    assert result is not None
    assert result.owner_discord_id == 123
    assert result.name == "Kennel"
    mock_session.flush.assert_awaited_once()


async def test_create_kennel_with_custom_name_and_limit():
    """create_kennel should respect custom name and pooch_limit."""
    fake_owner = SimpleNamespace(discord_id=123)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_kennel

        result = await create_kennel(123, name="My Kennel", pooch_limit=20)

    assert result.name == "My Kennel"
    assert result.pooch_limit == 20


# ---------------------------------------------------------------------------
# create_pooch
# ---------------------------------------------------------------------------


async def test_create_pooch_with_explicit_values():
    """create_pooch should set all explicit stat values on the created pooch."""
    scope_cls, mock_session = _mock_session_scope()
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.scalar = AsyncMock(return_value=None)

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_pooch

        result = await create_pooch(
            name="TestDog",
            sex="male",
            age=3,
            base_health=15,
            strength=12,
            cuteness=8,
            fluffiness=7,
            intelligence=11,
            dexterity=9,
            fertility=10,
            aggressiveness=5,
            size=10,
        )

    assert result.name == "TestDog"
    assert result.sex == "male"
    assert result.age == 3
    assert result.base_health == 15
    assert result.strength == 12
    assert result.cuteness == 8
    assert result.fluffiness == 7
    assert result.intelligence == 11
    assert result.dexterity == 9
    assert result.fertility == 10
    assert result.aggressiveness == 5
    assert result.size == 10
    assert result.alive is True
    assert result.virgin is True


async def test_create_pooch_vendor_clears_when_owner_given():
    """If both owner and vendor are given, vendor should be cleared."""
    fake_owner = SimpleNamespace(discord_id=1)
    fake_vendor = SimpleNamespace(id=2)
    scope_cls, mock_session = _mock_session_scope()
    mock_session.scalar = AsyncMock(return_value=None)
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=fake_vendor)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_pooch

        result = await create_pooch(
            owner_discord_id=1,
            vendor_id=2,
            name="Fido",
            sex="female",
            size=10,
        )

    assert result.owner_discord_id == 1
    assert result.vendor_id is None


# ---------------------------------------------------------------------------
# add_owner_to_server
# ---------------------------------------------------------------------------


async def test_add_owner_to_server():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import add_owner_to_server

        result = await add_owner_to_server(server_discord_id=111, owner_discord_id=222)

    assert result.server_discord_id == 111
    assert result.owner_discord_id == 222
    mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# add_pooch_to_kennel
# ---------------------------------------------------------------------------


async def test_add_pooch_to_kennel():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import add_pooch_to_kennel

        result = await add_pooch_to_kennel(kennel_id=1, pooch_id=2)

    assert result.kennel_id == 1
    assert result.pooch_id == 2


# ---------------------------------------------------------------------------
# create_pooch_pregnancy
# ---------------------------------------------------------------------------


async def test_create_pooch_pregnancy():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_pooch_pregnancy

        result = await create_pooch_pregnancy(mother_id=10, fetus_id=20)

    assert result.mother_id == 10
    assert result.fetus_id == 20


# ---------------------------------------------------------------------------
# bury_pooch
# ---------------------------------------------------------------------------


async def test_bury_pooch_returns_none_when_owner_missing():
    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
    ):
        from src.database.set import bury_pooch

        result = await bury_pooch(999, 1)

    assert result is None


async def test_bury_pooch_returns_none_when_pooch_missing():
    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=SimpleNamespace(discord_id=1))),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)),
    ):
        from src.database.set import bury_pooch

        result = await bury_pooch(1, 999)

    assert result is None
