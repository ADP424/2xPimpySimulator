"""Tests for src/database/utils/owner_event_filters.py.

These functions require an AsyncSession, so we mock the session and its
query results to test the filtering logic in isolation.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.database.utils.owner_event_filters import (
    _is_excluded,
    _normalize_name,
    _strip_requirement_metadata,
    check_owner_event_filter,
)

# ---------------------------------------------------------------------------
# _is_excluded
# ---------------------------------------------------------------------------


def test_is_excluded_returns_false_for_none():
    assert _is_excluded(5, None) is False


def test_is_excluded_returns_false_for_empty_list():
    assert _is_excluded(5, []) is False


def test_is_excluded_returns_true_when_present():
    assert _is_excluded(5, [3, 5, 7]) is True


def test_is_excluded_returns_false_when_absent():
    assert _is_excluded(5, [3, 7, 9]) is False


def test_is_excluded_converts_float_to_int():
    """The value should be converted to int before checking."""
    assert _is_excluded(5.0, [5]) is True


# ---------------------------------------------------------------------------
# _normalize_name
# ---------------------------------------------------------------------------


def test_normalize_name_strips_and_lowercases():
    assert _normalize_name("  Golden Retriever  ") == "golden retriever"


def test_normalize_name_empty_string():
    assert _normalize_name("") == ""


# ---------------------------------------------------------------------------
# _strip_requirement_metadata
# ---------------------------------------------------------------------------


def test_strip_requirement_metadata_removes_meta_keys():
    filter_spec = {
        "min_count": 1,
        "max_count": 5,
        "description": "test",
        "min_age": 2,
        "sex": "male",
    }
    result = _strip_requirement_metadata(filter_spec)
    assert "min_count" not in result
    assert "max_count" not in result
    assert "description" not in result
    assert result["min_age"] == 2
    assert result["sex"] == "male"


def test_strip_requirement_metadata_empty_dict():
    assert _strip_requirement_metadata({}) == {}


def test_strip_requirement_metadata_no_meta_keys():
    filter_spec = {"min_age": 1, "max_age": 10}
    result = _strip_requirement_metadata(filter_spec)
    assert result == filter_spec


# ---------------------------------------------------------------------------
# check_owner_event_filter
# ---------------------------------------------------------------------------


async def test_check_owner_event_filter_empty_filter_owner_exists():
    """An empty filter should pass if the owner exists."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=123)  # owner discord_id returned

    result = await check_owner_event_filter(mock_session, 123, {})
    assert result is True


async def test_check_owner_event_filter_empty_filter_owner_missing():
    """An empty filter should fail if the owner doesn't exist."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=None)

    result = await check_owner_event_filter(mock_session, 999, {})
    assert result is False


async def test_check_owner_event_filter_none_filter_owner_exists():
    """A None filter should pass if the owner exists."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=123)

    result = await check_owner_event_filter(mock_session, 123, None)
    assert result is True


async def test_check_owner_event_filter_money_filter_passes():
    """Filter with min_money should pass when owner has enough."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=500, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 2, 1])  # owner, pooch_count, kennel_count

    result = await check_owner_event_filter(mock_session, 1, {"min_money": 100})
    assert result is True


async def test_check_owner_event_filter_money_filter_fails():
    """Filter with min_money should fail when owner doesn't have enough."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=50, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 2, 1])

    result = await check_owner_event_filter(mock_session, 1, {"min_money": 100})
    assert result is False


async def test_check_owner_event_filter_max_money_filter_fails():
    """Filter with max_money should fail when owner exceeds it."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=500, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 0])

    result = await check_owner_event_filter(mock_session, 1, {"max_money": 100})
    assert result is False


async def test_check_owner_event_filter_exclude_money():
    """Filter with exclude_money should fail if owner's dollars are excluded."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=100, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 0])

    result = await check_owner_event_filter(mock_session, 1, {"exclude_money": [100, 200]})
    assert result is False


async def test_check_owner_event_filter_min_pooches_fails():
    """Filter with min_pooches should fail when owner has fewer pooches."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 1, 0])  # 1 pooch, 0 kennels

    result = await check_owner_event_filter(mock_session, 1, {"min_pooches": 5})
    assert result is False


async def test_check_owner_event_filter_max_pooches_fails():
    """Filter with max_pooches should fail when owner has more pooches."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 10, 0])

    result = await check_owner_event_filter(mock_session, 1, {"max_pooches": 5})
    assert result is False


async def test_check_owner_event_filter_owner_not_found():
    """Filter should fail when the owner doesn't exist in the database."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=None)

    result = await check_owner_event_filter(mock_session, 999, {"min_money": 0})
    assert result is False


async def test_check_owner_event_filter_bloodskull_min():
    """Filter with min_bloodskulls should pass when owner has enough."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=10)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 0])

    result = await check_owner_event_filter(mock_session, 1, {"min_bloodskulls": 5})
    assert result is True


async def test_check_owner_event_filter_bloodskull_max_fails():
    """Filter with max_bloodskulls should fail when owner exceeds it."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=10)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 0])

    result = await check_owner_event_filter(mock_session, 1, {"max_bloodskulls": 5})
    assert result is False


async def test_check_owner_event_filter_kennel_count():
    """Filter with min_kennels should pass when owner has enough kennels."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 3])

    result = await check_owner_event_filter(mock_session, 1, {"min_kennels": 2})
    assert result is True


async def test_check_owner_event_filter_kennel_count_fails():
    """Filter with min_kennels should fail when owner has fewer kennels."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 1])

    result = await check_owner_event_filter(mock_session, 1, {"min_kennels": 2})
    assert result is False
