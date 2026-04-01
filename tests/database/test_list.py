"""Tests for src/database/list.py.

Each function opens its own session_scope, so we mock it to inject fake data.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_scope(scalars_result=None, tuples_result=None, scalar_value=None):
    """
    Return an async context-manager that yields a mock session.
    """
    mock_session = AsyncMock()

    mock_response = MagicMock()
    if scalars_result is not None:
        mock_response.scalars.return_value.all.return_value = scalars_result
    if tuples_result is not None:
        mock_response.tuples.return_value.all.return_value = tuples_result
    mock_response.scalar_one_or_none.return_value = scalar_value

    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.scalar = AsyncMock(return_value=scalar_value)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _FakeScope, mock_session


# ---------------------------------------------------------------------------
# list_all_breeds
# ---------------------------------------------------------------------------


async def test_list_all_breeds_returns_breeds():
    """list_all_breeds should return all breeds from the database."""
    fake_breeds = [
        SimpleNamespace(id=1, name="Poodle", category="Water Dog"),
        SimpleNamespace(id=2, name="Labrador", category="Retriever"),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_breeds)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_all_breeds

        result = await list_all_breeds()

    assert len(result) == 2
    assert result[0].name == "Poodle"
    assert result[1].name == "Labrador"


async def test_list_all_breeds_returns_empty_list():
    """list_all_breeds should return an empty list when no breeds exist."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_all_breeds

        result = await list_all_breeds()

    assert result == []


# ---------------------------------------------------------------------------
# list_all_mutations
# ---------------------------------------------------------------------------


async def test_list_all_mutations_returns_mutations():
    """
    Test list all mutations returns mutations.

    Returns
    -------
    Any
        The result of calling `test_list_all_mutations_returns_mutations`.
    """

    fake_mutations = [SimpleNamespace(id=1, name="Cataracts", category="Blindness")]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_mutations)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_all_mutations

        result = await list_all_mutations()

    assert len(result) == 1
    assert result[0].name == "Cataracts"


# ---------------------------------------------------------------------------
# list_living_pooches
# ---------------------------------------------------------------------------


async def test_list_living_pooches_returns_alive_pooches():
    """
    Test list living pooches returns alive pooches.

    Returns
    -------
    Any
        The result of calling `test_list_living_pooches_returns_alive_pooches`.
    """

    fake_pooches = [
        SimpleNamespace(id=1, name="Buddy", alive=True),
        SimpleNamespace(id=2, name="Max", alive=True),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_pooches)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_living_pooches

        result = await list_living_pooches()

    assert len(result) == 2


async def test_list_living_pooches_returns_empty():
    """
    Test list living pooches returns empty.

    Returns
    -------
    Any
        The result of calling `test_list_living_pooches_returns_empty`.
    """

    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_living_pooches

        result = await list_living_pooches()

    assert result == []


# ---------------------------------------------------------------------------
# list_kennels_for_owner
# ---------------------------------------------------------------------------


async def test_list_kennels_for_owner_returns_empty_when_no_owner():
    """When the owner doesn't exist, return an empty list."""
    mock_session = AsyncMock()
    # First execute returns None for the owner lookup
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.list.session_scope", return_value=_FakeScope()):
        from src.database import list_kennels_for_owner

        result = await list_kennels_for_owner(999)

    assert result == []


# ---------------------------------------------------------------------------
# list_vendors
# ---------------------------------------------------------------------------


async def test_list_vendors_returns_vendors():
    """
    Test list vendors returns vendors.

    Returns
    -------
    Any
        The result of calling `test_list_vendors_returns_vendors`.
    """

    fake_vendors = [SimpleNamespace(id=1, name="Bob Smith", server_discord_id=123)]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_vendors)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_vendors

        result = await list_vendors(123)

    assert len(result) == 1
    assert result[0].name == "Bob Smith"


# ---------------------------------------------------------------------------
# list_servers
# ---------------------------------------------------------------------------


async def test_list_servers_returns_servers():
    """
    Test list servers returns servers.

    Returns
    -------
    Any
        The result of calling `test_list_servers_returns_servers`.
    """

    fake_servers = [SimpleNamespace(discord_id=111), SimpleNamespace(discord_id=222)]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_servers)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_servers

        result = await list_servers()

    assert len(result) == 2


# ---------------------------------------------------------------------------
# list_owners
# ---------------------------------------------------------------------------


async def test_list_owners_returns_all_owners():
    """
    Test list owners returns all owners.

    Returns
    -------
    Any
        The result of calling `test_list_owners_returns_all_owners`.
    """

    fake_owners = [SimpleNamespace(discord_id=1), SimpleNamespace(discord_id=2)]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_owners)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_owners

        result = await list_owners()

    assert len(result) == 2


# ---------------------------------------------------------------------------
# count_owners_for_server
# ---------------------------------------------------------------------------


async def test_count_owners_for_server_returns_count():
    """
    Test count owners for server returns count.

    Returns
    -------
    Any
        The result of calling `test_count_owners_for_server_returns_count`.
    """

    scope_cls, mock_session = _mock_session_scope(scalar_value=5)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import count_owners_for_server

        result = await count_owners_for_server(123)

    assert result == 5


async def test_count_owners_for_server_returns_zero_when_none():
    """
    Test count owners for server returns zero when none.

    Returns
    -------
    Any
        The result of calling `test_count_owners_for_server_returns_zero_when_none`.
    """

    scope_cls, mock_session = _mock_session_scope(scalar_value=None)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import count_owners_for_server

        result = await count_owners_for_server(123)

    assert result == 0
