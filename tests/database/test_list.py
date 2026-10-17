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


# ---------------------------------------------------------------------------
# list_active_sale_listings_for_server
# ---------------------------------------------------------------------------


async def test_list_active_sale_listings_for_server_returns_listings():
    """Should return all active listings on the server."""
    fake_listings = [
        SimpleNamespace(id=1, server_discord_id=10, is_active=True),
        SimpleNamespace(id=2, server_discord_id=10, is_active=True),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_listings)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_sale_listings_for_server

        result = await list_active_sale_listings_for_server(10)

    assert result == fake_listings


async def test_list_active_sale_listings_for_server_returns_empty():
    """Should return empty list when no active listings exist on the server."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_sale_listings_for_server

        result = await list_active_sale_listings_for_server(999)

    assert result == []


# ---------------------------------------------------------------------------
# list_active_sale_listings_for_owner
# ---------------------------------------------------------------------------


async def test_list_active_sale_listings_for_owner_returns_listings():
    """Should return all active listings by the seller."""
    fake_listings = [SimpleNamespace(id=3, seller_discord_id=42, is_active=True)]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_listings)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_sale_listings_for_owner

        result = await list_active_sale_listings_for_owner(42)

    assert result == fake_listings


async def test_list_active_sale_listings_for_owner_returns_empty():
    """Should return empty list when the owner has no active listings."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_sale_listings_for_owner

        result = await list_active_sale_listings_for_owner(999)

    assert result == []


# ---------------------------------------------------------------------------
# list_active_bounty_listings_for_server
# ---------------------------------------------------------------------------


async def test_list_active_bounty_listings_for_server_returns_listings():
    """Should return all active bounty listings on the server."""
    fake_bounties = [
        SimpleNamespace(id=10, server_discord_id=5, is_active=True),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_bounties)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_bounty_listings_for_server

        result = await list_active_bounty_listings_for_server(5)

    assert result == fake_bounties


async def test_list_active_bounty_listings_for_server_returns_empty():
    """Should return empty list when no bounties exist on the server."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_bounty_listings_for_server

        result = await list_active_bounty_listings_for_server(999)

    assert result == []


# ---------------------------------------------------------------------------
# list_active_bounty_listings_for_owner
# ---------------------------------------------------------------------------


async def test_list_active_bounty_listings_for_owner_returns_listings():
    """Should return all active bounties posted by the owner."""
    fake_bounties = [SimpleNamespace(id=20, buyer_discord_id=7, is_active=True)]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_bounties)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_bounty_listings_for_owner

        result = await list_active_bounty_listings_for_owner(7)

    assert result == fake_bounties


async def test_list_active_bounty_listings_for_owner_returns_empty():
    """Should return empty list when the owner has no active bounties."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_active_bounty_listings_for_owner

        result = await list_active_bounty_listings_for_owner(999)

    assert result == []


# ---------------------------------------------------------------------------
# list_bids_for_listing
# ---------------------------------------------------------------------------


async def test_list_bids_for_listing_returns_bids():
    """Should return all bids for the listing ordered by amount DESC."""
    fake_bids = [
        SimpleNamespace(id=1, listing_id=5, amount=300),
        SimpleNamespace(id=2, listing_id=5, amount=100),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_bids)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_bids_for_listing

        result = await list_bids_for_listing(5)

    assert result == fake_bids


async def test_list_bids_for_listing_returns_empty():
    """Should return empty list when no bids exist for the listing."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_bids_for_listing

        result = await list_bids_for_listing(999)

    assert result == []


# ---------------------------------------------------------------------------
# list_expired_sale_listings
# ---------------------------------------------------------------------------


async def test_list_expired_sale_listings_returns_expired():
    """Should return all active listings whose expiry time has passed."""
    fake_expired = [
        SimpleNamespace(id=8, is_active=True, expires_at="2020-01-01"),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_expired)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_expired_sale_listings

        result = await list_expired_sale_listings()

    assert result == fake_expired


async def test_list_expired_sale_listings_returns_empty_when_none():
    """Should return empty list when no listings have expired."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_expired_sale_listings

        result = await list_expired_sale_listings()

    assert result == []


# ---------------------------------------------------------------------------
# list_owner_bid_history
# ---------------------------------------------------------------------------


async def test_list_owner_bid_history_returns_bids():
    """Should return all bids placed by the owner, newest first."""
    fake_bids = [
        SimpleNamespace(id=3, bidder_discord_id=99, amount=200),
        SimpleNamespace(id=1, bidder_discord_id=99, amount=50),
    ]
    scope_cls, _ = _mock_session_scope(scalars_result=fake_bids)

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_owner_bid_history

        result = await list_owner_bid_history(99)

    assert result == fake_bids


async def test_list_owner_bid_history_returns_empty():
    """Should return empty list when the owner has never bid."""
    scope_cls, _ = _mock_session_scope(scalars_result=[])

    with patch("src.database.list.session_scope", return_value=scope_cls()):
        from src.database import list_owner_bid_history

        result = await list_owner_bid_history(999)

    assert result == []


# ---------------------------------------------------------------------------
# hourly tick queries
# ---------------------------------------------------------------------------


async def test_list_pooch_ids_on_breeding_cooldown():
    scope, _ = _mock_session_scope(scalars_result=[3, 4])
    with patch("src.database.list.session_scope", return_value=scope()):
        from src.database import list_pooch_ids_on_breeding_cooldown

        assert await list_pooch_ids_on_breeding_cooldown() == [3, 4]


async def test_list_pooch_ids_on_breeding_cooldown_leaves_out_pregnant_pooches():
    scope, session = _mock_session_scope(scalars_result=[])
    with patch("src.database.list.session_scope", return_value=scope()):
        from src.database import list_pooch_ids_on_breeding_cooldown

        await list_pooch_ids_on_breeding_cooldown()

    query = str(session.execute.await_args.args[0])
    assert "pooches.pregnancy_timer IS NULL" in query


async def test_list_persistent_injury_instances():
    scope, session = _mock_session_scope()
    response = MagicMock()
    response.all.return_value = [(10, 1), (11, 2)]
    session.execute = AsyncMock(return_value=response)
    with patch("src.database.list.session_scope", return_value=scope()):
        from src.database import list_persistent_injury_instances

        assert await list_persistent_injury_instances() == [(10, 1), (11, 2)]
