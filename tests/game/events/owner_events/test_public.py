"""Tests for src/game/events/owner_events/public.py."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOD = "src.game.events.owner_events.public"


@pytest.fixture(autouse=True)
def mock_get_current_season():
    """
    Mock get current season.

    Returns
    -------
    Any
        The result of calling `mock_get_current_season`.
    """

    with patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_active_event(
    id=1,
    owner_discord_id=123,
    event_id=10,
    responded_at=None,
    expires_at=None,
    context=None,
    result_summary=None,
    event=None,
):
    return SimpleNamespace(
        id=id,
        owner_discord_id=owner_discord_id,
        event_id=event_id,
        responded_at=responded_at,
        expires_at=expires_at,
        context=context or {},
        result_summary=result_summary,
        event=event or MagicMock(name="TestEvent", id=event_id, options=[]),
    )


def _make_option(
    id=1,
    is_default=False,
    label="Do it",
    actions=None,
    outcomes=None,
):
    return SimpleNamespace(
        id=id,
        is_default=is_default,
        label=label,
        actions=actions or [],
        outcomes=outcomes or [],
    )


# ---------------------------------------------------------------------------
# get_active_events_for_owner
# ---------------------------------------------------------------------------


class TestGetActiveEventsForOwner:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_events(self):
        from src.game.events.owner_events import get_active_events_for_owner

        with patch(f"{MOD}.list_active_owner_events_for_owner", new=AsyncMock(return_value=[])):
            result = await get_active_events_for_owner(123)

        assert result == []

    @pytest.mark.asyncio
    async def test_converts_active_events_to_triggered(self):
        from src.game.events.owner_events import get_active_events_for_owner

        mock_active = MagicMock()
        mock_triggered = MagicMock()

        with (
            patch(f"{MOD}.list_active_owner_events_for_owner", new=AsyncMock(return_value=[mock_active])),
            patch(f"{MOD}.to_triggered_owner_event", new=AsyncMock(return_value=mock_triggered)),
        ):
            result = await get_active_events_for_owner(123)

        assert result == [mock_triggered]


# ---------------------------------------------------------------------------
# get_event_history
# ---------------------------------------------------------------------------


class TestGetEventHistory:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_history(self):
        from src.game.events.owner_events import get_event_history

        with patch(f"{MOD}.list_owner_event_history_for_owner", new=AsyncMock(return_value=[])):
            result = await get_event_history(123)

        assert result == []

    @pytest.mark.asyncio
    async def test_converts_records_to_history_objects(self):
        from src.game.events.owner_events import get_event_history

        mock_record = MagicMock()
        mock_history = MagicMock()

        with (
            patch(f"{MOD}.list_owner_event_history_for_owner", new=AsyncMock(return_value=[mock_record])),
            patch(f"{MOD}.to_owner_event_history", new=AsyncMock(return_value=mock_history)),
        ):
            result = await get_event_history(123, limit=10)

        assert result == [mock_history]


# ---------------------------------------------------------------------------
# get_pending_event
# ---------------------------------------------------------------------------


class TestGetPendingEvent:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_pending_event(self):
        from src.game.events.owner_events import get_pending_event

        with patch(f"{MOD}.get_pending_active_owner_event", new=AsyncMock(return_value=None)):
            result = await get_pending_event(123)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_triggered_event_when_pending(self):
        from src.game.events.owner_events import get_pending_event

        mock_active = MagicMock()
        mock_triggered = MagicMock()

        with (
            patch(f"{MOD}.get_pending_active_owner_event", new=AsyncMock(return_value=mock_active)),
            patch(f"{MOD}.to_triggered_owner_event", new=AsyncMock(return_value=mock_triggered)),
        ):
            result = await get_pending_event(123)

        assert result is mock_triggered

    @pytest.mark.asyncio
    async def test_with_specific_event_id_returns_event(self):
        from src.game.events.owner_events import get_pending_event

        mock_active = _make_active_event(id=5, owner_discord_id=123, responded_at=None)
        mock_triggered = MagicMock()

        with (
            patch(f"{MOD}.get_active_owner_event_by_id", new=AsyncMock(return_value=mock_active)),
            patch(f"{MOD}.to_triggered_owner_event", new=AsyncMock(return_value=mock_triggered)),
        ):
            result = await get_pending_event(123, active_owner_event_id=5)

        assert result is mock_triggered

    @pytest.mark.asyncio
    async def test_with_specific_event_id_returns_none_when_not_found(self):
        from src.game.events.owner_events import get_pending_event

        with patch(f"{MOD}.get_active_owner_event_by_id", new=AsyncMock(return_value=None)):
            result = await get_pending_event(123, active_owner_event_id=99)

        assert result is None

    @pytest.mark.asyncio
    async def test_with_specific_event_id_returns_none_for_wrong_owner(self):
        from src.game.events.owner_events import get_pending_event

        mock_active = _make_active_event(id=5, owner_discord_id=999)  # different owner

        with patch(f"{MOD}.get_active_owner_event_by_id", new=AsyncMock(return_value=mock_active)):
            result = await get_pending_event(123, active_owner_event_id=5)

        assert result is None

    @pytest.mark.asyncio
    async def test_with_specific_event_id_returns_none_if_already_responded(self):
        from src.game.events.owner_events import get_pending_event

        mock_active = _make_active_event(id=5, owner_discord_id=123, responded_at=datetime.now(timezone.utc))

        with patch(f"{MOD}.get_active_owner_event_by_id", new=AsyncMock(return_value=mock_active)):
            result = await get_pending_event(123, active_owner_event_id=5)

        assert result is None


# ---------------------------------------------------------------------------
# list_all_owner_events
# ---------------------------------------------------------------------------


class TestListAllOwnerEvents:
    @pytest.mark.asyncio
    async def test_returns_converted_events(self):
        from src.game.events.owner_events import list_all_owner_events

        mock_event_orm = MagicMock()
        mock_event = MagicMock()

        with (
            patch(f"{MOD}.db_list_all_owner_events", new=AsyncMock(return_value=[mock_event_orm])),
            patch(f"{MOD}.to_owner_event", new=AsyncMock(return_value=mock_event)),
        ):
            result = await list_all_owner_events()

        assert result == [mock_event]


# ---------------------------------------------------------------------------
# run_hourly_event_check
# ---------------------------------------------------------------------------


class TestRunHourlyEventCheck:
    @pytest.mark.asyncio
    async def test_no_owners_returns_empty_dict(self):
        from src.game.events.owner_events import run_hourly_event_check

        with (
            patch(f"{MOD}.list_owners", new=AsyncMock(return_value=[])),
            patch(f"{MOD}.process_expired_events", new=AsyncMock(return_value=[])),
        ):
            result = await run_hourly_event_check()

        assert result == {}


# ---------------------------------------------------------------------------
# trigger_event_by_name
# ---------------------------------------------------------------------------


class TestTriggerEventByName:
    @pytest.mark.asyncio
    async def test_event_not_found_returns_none(self):
        from src.game.events.owner_events import trigger_event_by_name

        with patch(f"{MOD}.db_get_owner_event_by_name", new=AsyncMock(return_value=None)):
            result = await trigger_event_by_name(123, "nonexistent_event")

        assert result is None

    @pytest.mark.asyncio
    async def test_event_found_delegates_to_trigger_specific(self):
        from src.game.events.owner_events import trigger_event_by_name

        mock_event = MagicMock()
        mock_event.id = 42
        mock_triggered = MagicMock()

        with (
            patch(f"{MOD}.db_get_owner_event_by_name", new=AsyncMock(return_value=mock_event)),
            patch(f"{MOD}.trigger_specific_event", new=AsyncMock(return_value=mock_triggered)),
        ):
            result = await trigger_event_by_name(123, "test_event")

        assert result is mock_triggered


# ---------------------------------------------------------------------------
# Featured pooch gone (died / changed hands while the event waited)
# ---------------------------------------------------------------------------

_FEATURED_CONTEXT = {"extra_data": {"_featured_pooch_slot": "chosen_pooch", "chosen_pooch": {"pooch_ids": [7]}}}


def _pooch(alive=True, owner_discord_id=123, vendor_id=None):
    return SimpleNamespace(id=7, name="Lucy", alive=alive, owner_discord_id=owner_discord_id, vendor_id=vendor_id)


class TestUnavailableFeaturedPooch:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "pooch, expected",
        [
            (_pooch(), None),
            (_pooch(owner_discord_id=None), None),  # stray offered to the owner
            (_pooch(alive=False), "Lucy"),
            (_pooch(owner_discord_id=999), "Lucy"),
            (_pooch(owner_discord_id=None, vendor_id=4), "Lucy"),
        ],
    )
    async def test_names_pooch_only_when_gone(self, pooch, expected):
        from src.game.events.owner_events.public import get_unavailable_featured_pooch_name

        event = _make_active_event(context=_FEATURED_CONTEXT)
        with patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)):
            assert await get_unavailable_featured_pooch_name(event, 123) == expected

    @pytest.mark.asyncio
    async def test_event_without_featured_pooch_is_available(self):
        from src.game.events.owner_events.public import get_unavailable_featured_pooch_name

        lookup = AsyncMock()
        with patch("src.database.get_pooch_by_id", new=lookup):
            assert await get_unavailable_featured_pooch_name(_make_active_event(), 123) is None
        lookup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_respond_calls_off_event_for_dead_pooch(self):
        from src.game.events.owner_events import respond_to_event

        event = _make_active_event(context=_FEATURED_CONTEXT, event=SimpleNamespace(name="Interested Family"))
        option_lookup = AsyncMock()
        with (
            patch(f"{MOD}.get_active_owner_event_by_id", new=AsyncMock(return_value=event)),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=_pooch(alive=False))),
            patch(f"{MOD}.respond_to_active_owner_event", new=AsyncMock()) as respond,
            patch(f"{MOD}.archive_active_event", new=AsyncMock()) as archive,
            patch(f"{MOD}.get_owner_event_option_by_id", new=option_lookup),
        ):
            ok, message, result = await respond_to_event(123, 1, 5)

        assert ok is False
        assert message == "**Lucy** is no longer available, so **Interested Family** is off."
        assert result is None
        option_lookup.assert_not_awaited()
        respond.assert_awaited_once()
        assert respond.await_args.args[1] is None
        archive.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_hourly_check_calls_off_pending_event_for_dead_pooch(self):
        from src.game.events.owner_events import run_hourly_event_check

        event = _make_active_event(context=_FEATURED_CONTEXT, event=SimpleNamespace(name="Interested Family"))
        with (
            patch(f"{MOD}.list_expired_active_owner_events", new=AsyncMock(return_value=[])),
            patch(f"{MOD}.list_owners", new=AsyncMock(return_value=[SimpleNamespace(discord_id=123)])),
            patch(f"{MOD}.list_active_owner_events_for_owner", new=AsyncMock(return_value=[event])),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=_pooch(alive=False))),
            patch(f"{MOD}.respond_to_active_owner_event", new=AsyncMock()),
            patch(f"{MOD}.archive_active_event", new=AsyncMock()) as archive,
            patch(f"{MOD}.EVENT_HOURLY_TRIGGER_CHANCE", 0),
        ):
            assert await run_hourly_event_check(rng_seed=1) == {}

        archive.assert_awaited_once_with(1)
