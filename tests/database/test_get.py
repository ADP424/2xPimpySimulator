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
        from src.database import get_pooch_by_id

        result = await get_pooch_by_id(1)

    assert result is fake_pooch


async def test_get_pooch_by_id_returns_none():
    """When no pooch exists, the function should return None."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_by_id

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
        from src.database import get_owner_by_discord_id

        result = await get_owner_by_discord_id(123)

    assert result is fake_owner


async def test_get_owner_by_discord_id_returns_none_when_missing():
    """When no owner exists, the function should return None."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_owner_by_discord_id

        result = await get_owner_by_discord_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_breed_by_id / get_breed_by_name
# ---------------------------------------------------------------------------


async def test_get_breed_by_id_returns_breed():
    """
    Test get breed by id returns breed.

    Returns
    -------
    Any
        The result of calling `test_get_breed_by_id_returns_breed`.
    """

    fake_breed = SimpleNamespace(id=5, name="Poodle")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_breed)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_breed_by_id

        result = await get_breed_by_id(5)

    assert result is fake_breed


async def test_get_breed_by_name_returns_none_when_missing():
    """
    Test get breed by name returns none when missing.

    Returns
    -------
    Any
        The result of calling `test_get_breed_by_name_returns_none_when_missing`.
    """

    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_breed_by_name

        result = await get_breed_by_name("nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# get_mutation_by_id
# ---------------------------------------------------------------------------


async def test_get_mutation_by_id_returns_mutation():
    """
    Test get mutation by id returns mutation.

    Returns
    -------
    Any
        The result of calling `test_get_mutation_by_id_returns_mutation`.
    """

    fake_mutation = SimpleNamespace(id=3, name="Cataracts")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_mutation)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_mutation_by_id

        result = await get_mutation_by_id(3)

    assert result is fake_mutation


# ---------------------------------------------------------------------------
# get_kennel_by_id
# ---------------------------------------------------------------------------


async def test_get_kennel_by_id_returns_kennel():
    """
    Test get kennel by id returns kennel.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_by_id_returns_kennel`.
    """

    fake_kennel = SimpleNamespace(id=10, name="Main Kennel")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_kennel)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_kennel_by_id

        result = await get_kennel_by_id(10)

    assert result is fake_kennel


async def test_get_kennel_by_id_returns_none():
    """
    Test get kennel by id returns none.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_by_id_returns_none`.
    """

    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_kennel_by_id

        result = await get_kennel_by_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_random_breed_ids
# ---------------------------------------------------------------------------


async def test_get_random_breed_ids_returns_empty_for_zero():
    """Requesting 0 breed IDs should return an empty list without hitting the DB."""
    from src.database import get_random_breed_ids

    result = await get_random_breed_ids(0)
    assert result == []


async def test_get_random_breed_ids_returns_empty_for_negative():
    """Requesting negative breed IDs should return an empty list."""
    from src.database import get_random_breed_ids

    result = await get_random_breed_ids(-1)
    assert result == []


# ---------------------------------------------------------------------------
# get_vendor_by_id
# ---------------------------------------------------------------------------


async def test_get_vendor_by_id_returns_vendor():
    """
    Test get vendor by id returns vendor.

    Returns
    -------
    Any
        The result of calling `test_get_vendor_by_id_returns_vendor`.
    """

    fake_vendor = SimpleNamespace(id=7, name="Bob")
    scope_cls, _ = _mock_session_scope(scalar_result=fake_vendor)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_vendor_by_id

        result = await get_vendor_by_id(7)

    assert result is fake_vendor


# ---------------------------------------------------------------------------
# get_pooch_virginity_status
# ---------------------------------------------------------------------------


async def test_get_pooch_virginity_status_returns_bool():
    """
    Test get pooch virginity status returns bool.

    Returns
    -------
    Any
        The result of calling `test_get_pooch_virginity_status_returns_bool`.
    """

    scope_cls, _ = _mock_session_scope(scalar_result=True)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_virginity_status

        result = await get_pooch_virginity_status(1)

    assert result is True


async def test_get_pooch_virginity_status_returns_none_when_missing():
    """
    Test get pooch virginity status returns none when missing.

    Returns
    -------
    Any
        The result of calling `test_get_pooch_virginity_status_returns_none_when_missing`.
    """

    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_virginity_status

        result = await get_pooch_virginity_status(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_auction_sale_listing_by_id
# ---------------------------------------------------------------------------


async def test_get_auction_sale_listing_by_id_returns_listing():
    """When a sale listing exists, the function should return it."""
    fake_listing = SimpleNamespace(id=1, pooch_id=10, is_active=True)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=fake_listing)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.get.session_scope", return_value=_FakeScope()):
        from src.database import get_auction_sale_listing_by_id

        result = await get_auction_sale_listing_by_id(1)

    assert result is fake_listing


async def test_get_auction_sale_listing_by_id_returns_none():
    """When no listing exists, the function should return None."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.get.session_scope", return_value=_FakeScope()):
        from src.database import get_auction_sale_listing_by_id

        result = await get_auction_sale_listing_by_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_active_auction_sale_listing_for_pooch
# ---------------------------------------------------------------------------


async def test_get_active_auction_sale_listing_for_pooch_returns_listing():
    """When an active listing exists for the pooch, it should be returned."""
    fake_listing = SimpleNamespace(id=5, pooch_id=10, is_active=True)
    scope_cls, _ = _mock_session_scope(scalar_result=fake_listing)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_active_auction_sale_listing_for_pooch

        result = await get_active_auction_sale_listing_for_pooch(10)

    assert result is fake_listing


async def test_get_active_auction_sale_listing_for_pooch_returns_none():
    """When no active listing exists for the pooch, None should be returned."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_active_auction_sale_listing_for_pooch

        result = await get_active_auction_sale_listing_for_pooch(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_auction_bounty_listing_by_id
# ---------------------------------------------------------------------------


async def test_get_auction_bounty_listing_by_id_returns_listing():
    """When a bounty listing exists, the function should return it."""
    fake_listing = SimpleNamespace(id=3, buyer_discord_id=100, is_active=True)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=fake_listing)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.get.session_scope", return_value=_FakeScope()):
        from src.database import get_auction_bounty_listing_by_id

        result = await get_auction_bounty_listing_by_id(3)

    assert result is fake_listing


async def test_get_auction_bounty_listing_by_id_returns_none():
    """When no bounty listing exists, None should be returned."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.get.session_scope", return_value=_FakeScope()):
        from src.database import get_auction_bounty_listing_by_id

        result = await get_auction_bounty_listing_by_id(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_highest_bid_for_listing
# ---------------------------------------------------------------------------


async def test_get_highest_bid_for_listing_returns_bid():
    """When bids exist, the highest one should be returned."""
    fake_bid = SimpleNamespace(id=7, listing_id=1, amount=500, bidder_discord_id=42)
    scope_cls, _ = _mock_session_scope(scalar_result=fake_bid)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_highest_bid_for_listing

        result = await get_highest_bid_for_listing(1)

    assert result is fake_bid


async def test_get_highest_bid_for_listing_returns_none_when_no_bids():
    """When no bids exist for the listing, None should be returned."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_highest_bid_for_listing

        result = await get_highest_bid_for_listing(999)

    assert result is None


# ---------------------------------------------------------------------------
# get_pooch_injury_instance / get_pooch_disease_instance
# ---------------------------------------------------------------------------


async def test_get_pooch_injury_instance_returns_instance():
    """When the PoochInjury exists, it should be returned."""
    fake_pi = SimpleNamespace(id=3, pooch_id=1, injury=SimpleNamespace(name="Sprain"), pooch=SimpleNamespace(id=1))
    scope_cls, _ = _mock_session_scope(scalar_result=fake_pi)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_injury_instance

        result = await get_pooch_injury_instance(3)

    assert result is fake_pi


async def test_get_pooch_injury_instance_returns_none():
    """When the PoochInjury does not exist, None should be returned."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_injury_instance

        result = await get_pooch_injury_instance(999)

    assert result is None


async def test_get_pooch_disease_instance_returns_instance():
    """When the PoochDisease exists, it should be returned."""
    fake_pd = SimpleNamespace(id=4, pooch_id=1, disease=SimpleNamespace(name="Flu"), pooch=SimpleNamespace(id=1))
    scope_cls, _ = _mock_session_scope(scalar_result=fake_pd)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_disease_instance

        result = await get_pooch_disease_instance(4)

    assert result is fake_pd


async def test_get_pooch_disease_instance_returns_none():
    """When the PoochDisease does not exist, None should be returned."""
    scope_cls, _ = _mock_session_scope(scalar_result=None)

    with patch("src.database.get.session_scope", return_value=scope_cls()):
        from src.database import get_pooch_disease_instance

        result = await get_pooch_disease_instance(999)

    assert result is None
