"""Tests for src/database/utils/owner_event_filters.py.

These functions require an AsyncSession, so we mock the session and its
query results to test the filtering logic in isolation.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.database.utils import (
    check_owner_event_filter,
    is_excluded,
    normalize_name,
    strip_requirement_metadata,
)

# ---------------------------------------------------------------------------
# is_excluded
# ---------------------------------------------------------------------------


def test_is_excluded_returns_false_for_none():
    """
    Test is excluded returns false for none.

    Returns
    -------
    Any
        The result of calling `test_is_excluded_returns_false_for_none`.
    """

    assert is_excluded(5, None) is False


def test_is_excluded_returns_false_for_empty_list():
    """
    Test is excluded returns false for empty list.

    Returns
    -------
    Any
        The result of calling `test_is_excluded_returns_false_for_empty_list`.
    """

    assert is_excluded(5, []) is False


def test_is_excluded_returns_true_when_present():
    """
    Test is excluded returns true when present.

    Returns
    -------
    Any
        The result of calling `test_is_excluded_returns_true_when_present`.
    """

    assert is_excluded(5, [3, 5, 7]) is True


def test_is_excluded_returns_false_when_absent():
    """
    Test is excluded returns false when absent.

    Returns
    -------
    Any
        The result of calling `test_is_excluded_returns_false_when_absent`.
    """

    assert is_excluded(5, [3, 7, 9]) is False


def test_is_excluded_converts_float_to_int():
    """The value should be converted to int before checking."""
    assert is_excluded(5.0, [5]) is True


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


def test_normalize_name_strips_and_lowercases():
    """
    Test normalize name strips and lowercases.

    Returns
    -------
    Any
        The result of calling `test_normalize_name_strips_and_lowercases`.
    """

    assert normalize_name("  Golden Retriever  ") == "golden retriever"


def test_normalize_name_empty_string():
    """
    Test normalize name empty string.

    Returns
    -------
    Any
        The result of calling `test_normalize_name_empty_string`.
    """

    assert normalize_name("") == ""


# ---------------------------------------------------------------------------
# strip_requirement_metadata
# ---------------------------------------------------------------------------


def test_strip_requirement_metadata_removes_meta_keys():
    """
    Test strip requirement metadata removes meta keys.

    Returns
    -------
    Any
        The result of calling `test_strip_requirement_metadata_removes_meta_keys`.
    """

    filter_spec = {
        "min_count": 1,
        "max_count": 5,
        "description": "test",
        "min_age": 2,
        "sex": "male",
    }
    result = strip_requirement_metadata(filter_spec)
    assert "min_count" not in result
    assert "max_count" not in result
    assert "description" not in result
    assert result["min_age"] == 2
    assert result["sex"] == "male"


def test_strip_requirement_metadata_empty_dict():
    """
    Test strip requirement metadata empty dict.

    Returns
    -------
    Any
        The result of calling `test_strip_requirement_metadata_empty_dict`.
    """

    assert strip_requirement_metadata({}) == {}


def test_strip_requirement_metadata_no_meta_keys():
    """
    Test strip requirement metadata no meta keys.

    Returns
    -------
    Any
        The result of calling `test_strip_requirement_metadata_no_meta_keys`.
    """

    filter_spec = {"min_age": 1, "max_age": 10}
    result = strip_requirement_metadata(filter_spec)
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


async def test_check_owner_event_filter_max_kennels_fails():
    """Filter with max_kennels should fail when owner exceeds it."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 5])

    result = await check_owner_event_filter(mock_session, 1, {"max_kennels": 3})
    assert result is False


async def test_check_owner_event_filter_exclude_pooches():
    """Filter with exclude_pooches should fail when owner's pooch count is excluded."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 3, 0])

    result = await check_owner_event_filter(mock_session, 1, {"exclude_pooches": [3]})
    assert result is False


async def test_check_owner_event_filter_exclude_kennels():
    """Filter with exclude_kennels should fail when owner's kennel count is excluded."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=0)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 2])

    result = await check_owner_event_filter(mock_session, 1, {"exclude_kennels": [2]})
    assert result is False


async def test_check_owner_event_filter_exclude_bloodskulls():
    """Filter with exclude_bloodskulls should fail when owner's value is excluded."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=0, bloodskulls=5)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 0, 0])

    result = await check_owner_event_filter(mock_session, 1, {"exclude_bloodskulls": [5]})
    assert result is False


async def test_check_owner_event_filter_passes_all_checks():
    """A filter that all conditions pass should return True."""
    fake_owner = SimpleNamespace(discord_id=1, dollars=200, bloodskulls=3)
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[fake_owner, 2, 1])

    result = await check_owner_event_filter(
        mock_session,
        1,
        {"min_money": 100, "max_money": 500, "min_pooches": 1, "max_pooches": 5, "min_kennels": 1},
    )
    assert result is True


# ---------------------------------------------------------------------------
# count_matching_pooches_for_owner / get_matching_pooch_ids_for_owner
# ---------------------------------------------------------------------------


import random as _random

from src.database.utils import (
    check_server_event_filter,
    check_stray_event_filter,
    count_matching_kennels_for_owner,
    count_matching_pooches_for_owner,
    count_matching_stray_pooches_for_server,
    get_matching_kennel_ids_for_owner,
    get_matching_pooch_ids_for_owner,
    get_matching_stray_pooch_ids_for_server,
    get_random_matching_kennel_id_for_owner,
    get_random_matching_pooch_id_for_owner,
)


async def test_count_matching_pooches_for_owner():
    """
    Test count matching pooches for owner.

    Returns
    -------
    Any
        The result of calling `test_count_matching_pooches_for_owner`.
    """

    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = []
    count_result = AsyncMock(return_value=3)
    mock_session.execute = AsyncMock(return_value=query_result)
    mock_session.scalar = count_result

    result = await count_matching_pooches_for_owner(mock_session, 1, None)
    assert result == 3


async def test_count_matching_pooches_for_owner_returns_zero_on_none():
    """
    Test count matching pooches for owner returns zero on none.

    Returns
    -------
    Any
        The result of calling `test_count_matching_pooches_for_owner_returns_zero_on_none`.
    """

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=None)
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await count_matching_pooches_for_owner(mock_session, 1, None)
    assert result == 0


async def test_get_matching_pooch_ids_for_owner():
    """
    Test get matching pooch ids for owner.

    Returns
    -------
    Any
        The result of calling `test_get_matching_pooch_ids_for_owner`.
    """

    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [10, 20, 30]
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await get_matching_pooch_ids_for_owner(mock_session, 1, None)
    assert result == [10, 20, 30]


async def test_get_random_matching_pooch_id_returns_none_when_no_matches():
    """
    Test get random matching pooch id returns none when no matches.

    Returns
    -------
    Any
        The result of calling `test_get_random_matching_pooch_id_returns_none_when_no_matches`.
    """

    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await get_random_matching_pooch_id_for_owner(mock_session, 1, None, _random.Random(42))
    assert result is None


async def test_get_random_matching_pooch_id_returns_one_of_ids():
    """
    Test get random matching pooch id returns one of ids.

    Returns
    -------
    Any
        The result of calling `test_get_random_matching_pooch_id_returns_one_of_ids`.
    """

    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [5, 10, 15]
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await get_random_matching_pooch_id_for_owner(mock_session, 1, None, _random.Random(42))
    assert result in [5, 10, 15]


# ---------------------------------------------------------------------------
# get_matching_kennel_ids_for_owner / count / random
# ---------------------------------------------------------------------------


async def test_get_matching_kennel_ids_for_owner_no_nested_filters():
    """Without nested pooch filters, returns all candidate kennel IDs."""
    mock_session = AsyncMock()
    kennel_result = MagicMock()
    kennel_result.scalars.return_value.all.return_value = [1, 2, 3]
    mock_session.execute = AsyncMock(return_value=kennel_result)

    result = await get_matching_kennel_ids_for_owner(mock_session, 100, None)
    assert result == [1, 2, 3]


async def test_count_matching_kennels_for_owner():
    """
    Test count matching kennels for owner.

    Returns
    -------
    Any
        The result of calling `test_count_matching_kennels_for_owner`.
    """

    mock_session = AsyncMock()
    kennel_result = MagicMock()
    kennel_result.scalars.return_value.all.return_value = [1, 2]
    mock_session.execute = AsyncMock(return_value=kennel_result)

    result = await count_matching_kennels_for_owner(mock_session, 100, None)
    assert result == 2


async def test_get_random_matching_kennel_id_returns_none_when_empty():
    """
    Test get random matching kennel id returns none when empty.

    Returns
    -------
    Any
        The result of calling `test_get_random_matching_kennel_id_returns_none_when_empty`.
    """

    mock_session = AsyncMock()
    kennel_result = MagicMock()
    kennel_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=kennel_result)

    result = await get_random_matching_kennel_id_for_owner(mock_session, 100, None, _random.Random(0))
    assert result is None


async def test_get_random_matching_kennel_id_returns_one_of_ids():
    """
    Test get random matching kennel id returns one of ids.

    Returns
    -------
    Any
        The result of calling `test_get_random_matching_kennel_id_returns_one_of_ids`.
    """

    mock_session = AsyncMock()
    kennel_result = MagicMock()
    kennel_result.scalars.return_value.all.return_value = [10, 20]
    mock_session.execute = AsyncMock(return_value=kennel_result)

    result = await get_random_matching_kennel_id_for_owner(mock_session, 100, None, _random.Random(0))
    assert result in [10, 20]


# ---------------------------------------------------------------------------
# check_stray_event_filter
# ---------------------------------------------------------------------------


async def test_check_stray_event_filter_empty_filter_no_strays():
    """Empty filter fails if there are no alive strays."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=0)

    result = await check_stray_event_filter(mock_session, 200, None)
    assert result is False


async def test_check_stray_event_filter_empty_filter_with_strays():
    """Empty filter passes if there's at least one alive stray."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=2)

    result = await check_stray_event_filter(mock_session, 200, None)
    assert result is True


async def test_check_stray_event_filter_with_pooch_filters_pass():
    """Stray event filter with a pooch sub-filter that passes."""
    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [1, 2, 3]
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await check_stray_event_filter(mock_session, 200, {"pooches": [{"min_count": 2}]})
    assert result is True


async def test_check_stray_event_filter_with_pooch_filters_fail():
    """Stray event filter with a pooch sub-filter that fails (not enough matches)."""
    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [1]
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await check_stray_event_filter(mock_session, 200, {"pooches": [{"min_count": 5}]})
    assert result is False


# ---------------------------------------------------------------------------
# get_matching_stray_pooch_ids_for_server / count
# ---------------------------------------------------------------------------


async def test_get_matching_stray_pooch_ids_for_server():
    """
    Test get matching stray pooch ids for server.

    Returns
    -------
    Any
        The result of calling `test_get_matching_stray_pooch_ids_for_server`.
    """

    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [100, 200]
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await get_matching_stray_pooch_ids_for_server(mock_session, 200, None)
    assert result == [100, 200]


async def test_count_matching_stray_pooches_for_server():
    """
    Test count matching stray pooches for server.

    Returns
    -------
    Any
        The result of calling `test_count_matching_stray_pooches_for_server`.
    """

    mock_session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [1, 2, 3]
    mock_session.execute = AsyncMock(return_value=query_result)

    result = await count_matching_stray_pooches_for_server(mock_session, 200, None)
    assert result == 3


# ---------------------------------------------------------------------------
# check_server_event_filter
# ---------------------------------------------------------------------------


async def test_check_server_event_filter_none_filter():
    """No filter should always return True."""
    mock_session = AsyncMock()
    result = await check_server_event_filter(mock_session, 200, None)
    assert result is True


async def test_check_server_event_filter_min_owners_fails():
    """Should fail when server has fewer owners than required."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=1)

    result = await check_server_event_filter(mock_session, 200, {"min_owners": 5})
    assert result is False


async def test_check_server_event_filter_max_owners_fails():
    """Should fail when server has more owners than allowed."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=10)

    result = await check_server_event_filter(mock_session, 200, {"max_owners": 3})
    assert result is False


async def test_check_server_event_filter_min_owners_passes():
    """Should pass when server meets the min_owners requirement."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=5)

    result = await check_server_event_filter(mock_session, 200, {"min_owners": 3})
    assert result is True
