"""Tests for src/game/manage_owner_events/public.py."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_get_current_season():
    with patch("src.game.manage_owner_events.public.get_current_season", new=AsyncMock(return_value="spring")):
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
    event_id=10,
    is_visible=True,
    is_default=False,
    label="Do it",
    min_money=0,
    min_bloodskulls=0,
    filter=None,
    actions=None,
    outcomes=None,
):
    return SimpleNamespace(
        id=id,
        event_id=event_id,
        is_visible=is_visible,
        is_default=is_default,
        label=label,
        min_money=min_money,
        min_bloodskulls=min_bloodskulls,
        filter=filter or {},
        actions=actions or [],
        outcomes=outcomes or [],
    )


# ---------------------------------------------------------------------------
# get_active_events_for_owner
# ---------------------------------------------------------------------------


class TestGetActiveEventsForOwner:
    async def test_returns_empty_list_when_no_events(self):
        from src.game.manage_owner_events.public import get_active_events_for_owner

        with patch(
            "src.game.manage_owner_events.public.list_active_owner_events_for_owner",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await get_active_events_for_owner(123)

        assert result == []

    async def test_converts_active_events_to_triggered(self):
        from src.game.manage_owner_events.public import get_active_events_for_owner

        mock_active = MagicMock()
        mock_triggered = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.list_active_owner_events_for_owner",
                new_callable=AsyncMock,
                return_value=[mock_active],
            ),
            patch(
                "src.game.manage_owner_events.public.to_triggered_owner_event",
                new_callable=AsyncMock,
                return_value=mock_triggered,
            ),
        ):
            result = await get_active_events_for_owner(123)

        assert result == [mock_triggered]


# ---------------------------------------------------------------------------
# get_event_history
# ---------------------------------------------------------------------------


class TestGetEventHistory:
    async def test_returns_empty_list_when_no_history(self):
        from src.game.manage_owner_events.public import get_event_history

        with patch(
            "src.game.manage_owner_events.public.list_owner_event_history_for_owner",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await get_event_history(123)

        assert result == []

    async def test_converts_records_to_history_objects(self):
        from src.game.manage_owner_events.public import get_event_history

        mock_record = MagicMock()
        mock_history = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.list_owner_event_history_for_owner",
                new_callable=AsyncMock,
                return_value=[mock_record],
            ),
            patch(
                "src.game.manage_owner_events.public.to_owner_event_history",
                new_callable=AsyncMock,
                return_value=mock_history,
            ),
        ):
            result = await get_event_history(123, limit=10)

        assert result == [mock_history]


# ---------------------------------------------------------------------------
# get_pending_event
# ---------------------------------------------------------------------------


class TestGetPendingEvent:
    async def test_returns_none_when_no_pending_event(self):
        from src.game.manage_owner_events.public import get_pending_event

        with patch(
            "src.game.manage_owner_events.public.get_pending_active_owner_event",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_pending_event(123)

        assert result is None

    async def test_returns_triggered_event_when_pending(self):
        from src.game.manage_owner_events.public import get_pending_event

        mock_active = MagicMock()
        mock_triggered = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.get_pending_active_owner_event",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.to_triggered_owner_event",
                new_callable=AsyncMock,
                return_value=mock_triggered,
            ),
        ):
            result = await get_pending_event(123)

        assert result is mock_triggered

    async def test_with_specific_event_id_returns_event(self):
        from src.game.manage_owner_events.public import get_pending_event

        mock_active = _make_active_event(id=5, owner_discord_id=123, responded_at=None)
        mock_triggered = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.to_triggered_owner_event",
                new_callable=AsyncMock,
                return_value=mock_triggered,
            ),
        ):
            result = await get_pending_event(123, active_owner_event_id=5)

        assert result is mock_triggered

    async def test_with_specific_event_id_returns_none_when_not_found(self):
        from src.game.manage_owner_events.public import get_pending_event

        with patch(
            "src.game.manage_owner_events.public.get_active_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_pending_event(123, active_owner_event_id=99)

        assert result is None

    async def test_with_specific_event_id_returns_none_for_wrong_owner(self):
        from src.game.manage_owner_events.public import get_pending_event

        mock_active = _make_active_event(id=5, owner_discord_id=999)  # different owner

        with patch(
            "src.game.manage_owner_events.public.get_active_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=mock_active,
        ):
            result = await get_pending_event(123, active_owner_event_id=5)

        assert result is None

    async def test_with_specific_event_id_returns_none_if_already_responded(self):
        from datetime import datetime, timezone

        from src.game.manage_owner_events.public import get_pending_event

        mock_active = _make_active_event(id=5, owner_discord_id=123, responded_at=datetime.now(timezone.utc))

        with patch(
            "src.game.manage_owner_events.public.get_active_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=mock_active,
        ):
            result = await get_pending_event(123, active_owner_event_id=5)

        assert result is None


# ---------------------------------------------------------------------------
# list_all_owner_events
# ---------------------------------------------------------------------------


class TestListAllOwnerEvents:
    async def test_returns_converted_events(self):
        from src.game.manage_owner_events.public import list_all_owner_events

        mock_event_orm = MagicMock()
        mock_event = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.db_list_all_owner_events",
                new_callable=AsyncMock,
                return_value=[mock_event_orm],
            ),
            patch(
                "src.game.manage_owner_events.public.to_owner_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
        ):
            result = await list_all_owner_events()

        assert result == [mock_event]

    async def test_returns_empty_list_when_none(self):
        from src.game.manage_owner_events.public import list_all_owner_events

        with patch(
            "src.game.manage_owner_events.public.db_list_all_owner_events",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await list_all_owner_events()

        assert result == []


# ---------------------------------------------------------------------------
# process_expired_events
# ---------------------------------------------------------------------------


class TestProcessExpiredEvents:
    async def test_returns_empty_list_when_no_expired(self):
        from src.game.manage_owner_events.public import process_expired_events

        with patch(
            "src.game.manage_owner_events.public.list_expired_active_owner_events",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await process_expired_events()

        assert result == []

    async def test_creates_rng_when_not_provided(self):
        from src.game.manage_owner_events.public import process_expired_events

        with patch(
            "src.game.manage_owner_events.public.list_expired_active_owner_events",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await process_expired_events(rng=None)

        assert result == []

    async def test_processes_expired_event_with_default_option(self):
        from src.game.manage_owner_events.public import process_expired_events
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        default_opt = _make_option(id=1, is_default=True, label="Give up", actions=[])
        mock_event = MagicMock()
        mock_event.name = "Test Event"
        mock_event.options = [default_opt]

        active_event = _make_active_event(
            id=7,
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
            result_summary=None,
            event=mock_event,
        )

        empty_result = OwnerEventResult()

        with (
            patch(
                "src.game.manage_owner_events.public.list_expired_active_owner_events",
                new_callable=AsyncMock,
                return_value=[active_event],
            ),
            patch(
                "src.game.manage_owner_events.public.execute_event_actions",
                new_callable=AsyncMock,
                return_value=empty_result,
            ),
            patch(
                "src.game.manage_owner_events.public.choose_option_outcome",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            results = await process_expired_events(rng=random.Random(42))

        assert len(results) == 1
        owner_id, _, result = results[0]
        assert owner_id == 123
        assert "expired" in result.message.lower() or "Give up" in result.message

    async def test_processes_expired_event_with_outcome(self):
        from src.game.manage_owner_events.public import process_expired_events
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        default_opt = _make_option(id=1, is_default=True, label="Give up", actions=[])
        mock_event = MagicMock()
        mock_event.name = "Test Event"
        mock_event.options = [default_opt]

        active_event = _make_active_event(
            id=7,
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
            result_summary=None,
            event=mock_event,
        )

        mock_outcome = SimpleNamespace(
            id=99,
            label="Outcome A",
            description="desc",
            message="You lost!",
            chance=1.0,
            actions=[],
        )
        empty_result = OwnerEventResult()

        with (
            patch(
                "src.game.manage_owner_events.public.list_expired_active_owner_events",
                new_callable=AsyncMock,
                return_value=[active_event],
            ),
            patch(
                "src.game.manage_owner_events.public.execute_event_actions",
                new_callable=AsyncMock,
                return_value=empty_result,
            ),
            patch(
                "src.game.manage_owner_events.public.choose_option_outcome",
                new_callable=AsyncMock,
                return_value=mock_outcome,
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            results = await process_expired_events(rng=random.Random(42))

        assert len(results) == 1
        _, _, result = results[0]
        assert result.message == "You lost!"
        assert result.extra_data["selected_outcome"]["id"] == 99

    async def test_processes_expired_event_no_default_option(self):
        from src.game.manage_owner_events.public import process_expired_events

        mock_event = MagicMock()
        mock_event.name = "Test Event"
        mock_event.options = []

        active_event = _make_active_event(
            id=7,
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
            result_summary=None,
            event=mock_event,
        )

        with (
            patch(
                "src.game.manage_owner_events.public.list_expired_active_owner_events",
                new_callable=AsyncMock,
                return_value=[active_event],
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            results = await process_expired_events(rng=random.Random(42))

        assert len(results) == 1
        _, _, result = results[0]
        assert "expired" in result.message.lower()

    async def test_uses_existing_result_summary_when_present(self):
        from src.game.manage_owner_events.public import process_expired_events
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        mock_event = MagicMock()
        mock_event.name = "Test Event"
        mock_event.options = []

        existing_result = OwnerEventResult(message="prior message")
        active_event = _make_active_event(
            id=7,
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
            result_summary=existing_result.to_dict(),
            event=mock_event,
        )

        with (
            patch(
                "src.game.manage_owner_events.public.list_expired_active_owner_events",
                new_callable=AsyncMock,
                return_value=[active_event],
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            results = await process_expired_events(rng=random.Random(42))

        assert len(results) == 1


# ---------------------------------------------------------------------------
# respond_to_event
# ---------------------------------------------------------------------------


class TestRespondToEvent:
    async def test_returns_false_when_event_not_found(self):
        from src.game.manage_owner_events.public import respond_to_event

        with patch(
            "src.game.manage_owner_events.public.get_active_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "not found" in msg.lower()
        assert result is None

    async def test_returns_false_when_wrong_owner(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=999)

        with patch(
            "src.game.manage_owner_events.public.get_active_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=mock_active,
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "not for you" in msg.lower()

    async def test_returns_false_when_already_responded(self):
        from datetime import datetime, timezone

        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, responded_at=datetime.now(timezone.utc))

        with patch(
            "src.game.manage_owner_events.public.get_active_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=mock_active,
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "already responded" in msg.lower()

    async def test_returns_false_when_expired(self):
        from datetime import datetime, timedelta, timezone

        from src.game.manage_owner_events.public import respond_to_event

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_active = _make_active_event(owner_discord_id=123, expires_at=past)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "expired" in msg.lower()

    async def test_returns_false_when_option_not_found(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 99)

        assert ok is False
        assert "invalid option" in msg.lower()

    async def test_returns_false_when_option_for_wrong_event(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, event_id=10)
        mock_option = _make_option(event_id=99)  # different event

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "not valid" in msg.lower()

    async def test_returns_false_when_option_not_visible(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, event_id=10)
        mock_option = _make_option(event_id=10, is_visible=False)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "not available" in msg.lower()

    async def test_returns_false_when_owner_not_found(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, event_id=10)
        mock_option = _make_option(event_id=10, is_visible=True)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "owner not found" in msg.lower()

    async def test_returns_false_when_insufficient_money(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, event_id=10)
        mock_option = _make_option(event_id=10, is_visible=True, min_money=100)
        mock_owner = SimpleNamespace(dollars=50, bloodskulls=100)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=mock_owner,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "$100" in msg

    async def test_returns_false_when_insufficient_bloodskulls(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, event_id=10)
        mock_option = _make_option(event_id=10, is_visible=True, min_money=0, min_bloodskulls=5)
        mock_owner = SimpleNamespace(dollars=999, bloodskulls=2)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=mock_owner,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "5 bloodskulls" in msg

    async def test_returns_false_when_filter_fails(self):
        from src.game.manage_owner_events.public import respond_to_event

        mock_active = _make_active_event(owner_discord_id=123, event_id=10)
        mock_option = _make_option(event_id=10, is_visible=True, min_money=0, min_bloodskulls=0)
        mock_owner = SimpleNamespace(dollars=999, bloodskulls=999)

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=mock_owner,
            ),
            patch(
                "src.game.manage_owner_events.public.check_owner_event_filter_for_owner",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is False
        assert "requirements" in msg.lower()

    async def test_successful_response_without_outcome(self):
        from src.game.manage_owner_events.public import respond_to_event
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        mock_active = _make_active_event(
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
        )
        mock_option = _make_option(event_id=10, is_visible=True, label="Accept")
        mock_owner = SimpleNamespace(dollars=999, bloodskulls=999)
        empty_result = OwnerEventResult()

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=mock_owner,
            ),
            patch(
                "src.game.manage_owner_events.public.check_owner_event_filter_for_owner",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "src.game.manage_owner_events.public.execute_event_actions",
                new_callable=AsyncMock,
                return_value=empty_result,
            ),
            patch(
                "src.game.manage_owner_events.public.choose_option_outcome",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is True
        assert "Accept" in msg
        assert result is not None

    async def test_successful_response_with_outcome(self):
        from src.game.manage_owner_events.public import respond_to_event
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        mock_active = _make_active_event(
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
            result_summary=None,
        )
        mock_option = _make_option(event_id=10, is_visible=True, label="Fight")
        mock_owner = SimpleNamespace(dollars=999, bloodskulls=999)
        empty_result = OwnerEventResult()
        mock_outcome = SimpleNamespace(
            id=5,
            label="Victory",
            description="you won",
            message="You won!",
            chance=1.0,
            actions=[],
        )

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=mock_owner,
            ),
            patch(
                "src.game.manage_owner_events.public.check_owner_event_filter_for_owner",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "src.game.manage_owner_events.public.execute_event_actions",
                new_callable=AsyncMock,
                return_value=empty_result,
            ),
            patch(
                "src.game.manage_owner_events.public.choose_option_outcome",
                new_callable=AsyncMock,
                return_value=mock_outcome,
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is True
        assert msg == "You won!"
        assert result.extra_data["selected_outcome"]["id"] == 5

    async def test_merges_existing_result_summary(self):
        from src.game.manage_owner_events.public import respond_to_event
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        existing = OwnerEventResult(pooches_affected=[42])
        mock_active = _make_active_event(
            owner_discord_id=123,
            event_id=10,
            context={"affected_pooch_ids": [], "extra_data": {}},
            result_summary=existing.to_dict(),
        )
        mock_option = _make_option(event_id=10, is_visible=True)
        mock_owner = SimpleNamespace(dollars=999, bloodskulls=999)
        empty_result = OwnerEventResult()

        with (
            patch(
                "src.game.manage_owner_events.public.get_active_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_active,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_event_option_by_id",
                new_callable=AsyncMock,
                return_value=mock_option,
            ),
            patch(
                "src.game.manage_owner_events.public.get_owner_by_discord_id",
                new_callable=AsyncMock,
                return_value=mock_owner,
            ),
            patch(
                "src.game.manage_owner_events.public.check_owner_event_filter_for_owner",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "src.game.manage_owner_events.public.execute_event_actions",
                new_callable=AsyncMock,
                return_value=empty_result,
            ),
            patch(
                "src.game.manage_owner_events.public.choose_option_outcome",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.game.manage_owner_events.public.respond_to_active_owner_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.game.manage_owner_events.public.archive_active_event",
                new_callable=AsyncMock,
            ),
        ):
            ok, msg, result = await respond_to_event(123, 1, 1)

        assert ok is True
        assert 42 in result.pooches_affected


# ---------------------------------------------------------------------------
# run_hourly_event_check
# ---------------------------------------------------------------------------


class TestRunHourlyEventCheck:
    async def test_returns_empty_dict_when_no_owners(self):
        from src.game.manage_owner_events.public import run_hourly_event_check

        with (
            patch(
                "src.game.manage_owner_events.public.process_expired_events",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.list_owners",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await run_hourly_event_check(rng_seed=42)

        assert result == {}

    async def test_triggers_event_for_owner_above_chance(self):
        from src.game.manage_owner_events.public import run_hourly_event_check

        mock_owner = SimpleNamespace(discord_id=123)
        mock_event = MagicMock()

        # Use rng_seed=0 so random() produces a predictable value below EVENT_HOURLY_TRIGGER_CHANCE (1.0)
        with (
            patch(
                "src.game.manage_owner_events.public.process_expired_events",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.list_owners",
                new_callable=AsyncMock,
                return_value=[mock_owner],
            ),
            patch(
                "src.game.manage_owner_events.public.EVENT_HOURLY_TRIGGER_CHANCE",
                new=1.0,
            ),
            patch(
                "src.game.manage_owner_events.public.trigger_random_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
        ):
            result = await run_hourly_event_check(rng_seed=42)

        assert 123 in result
        assert mock_event in result[123]

    async def test_skips_owner_when_no_event_triggered(self):
        from src.game.manage_owner_events.public import run_hourly_event_check

        mock_owner = SimpleNamespace(discord_id=123)

        with (
            patch(
                "src.game.manage_owner_events.public.process_expired_events",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.list_owners",
                new_callable=AsyncMock,
                return_value=[mock_owner],
            ),
            patch(
                "src.game.manage_owner_events.public.EVENT_HOURLY_TRIGGER_CHANCE",
                new=1.0,
            ),
            patch(
                "src.game.manage_owner_events.public.trigger_random_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await run_hourly_event_check(rng_seed=42)

        assert result == {}

    async def test_uses_seeded_rng(self):
        from src.game.manage_owner_events.public import run_hourly_event_check

        with (
            patch(
                "src.game.manage_owner_events.public.process_expired_events",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.list_owners",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await run_hourly_event_check(rng_seed=999)

        assert result == {}

    async def test_uses_unseeded_rng_when_no_seed(self):
        from src.game.manage_owner_events.public import run_hourly_event_check

        with (
            patch(
                "src.game.manage_owner_events.public.process_expired_events",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.list_owners",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await run_hourly_event_check()

        assert result == {}


# ---------------------------------------------------------------------------
# trigger_random_event
# ---------------------------------------------------------------------------


class TestTriggerRandomEvent:
    async def test_returns_none_when_max_active_events(self):
        from src.game.manage_owner_events.public import trigger_random_event

        mock_events = [MagicMock(), MagicMock(), MagicMock()]

        with (
            patch(
                "src.game.manage_owner_events.public.list_active_owner_events_for_owner",
                new_callable=AsyncMock,
                return_value=mock_events,
            ),
            patch(
                "src.game.manage_owner_events.public.EVENT_MAX_ACTIVE_PER_OWNER",
                new=3,
            ),
        ):
            result = await trigger_random_event(123)

        assert result is None

    async def test_returns_none_when_no_eligible_event(self):
        from src.game.manage_owner_events.public import trigger_random_event

        with (
            patch(
                "src.game.manage_owner_events.public.list_active_owner_events_for_owner",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.get_random_eligible_owner_event_for_owner",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await trigger_random_event(123)

        assert result is None

    async def test_returns_triggered_event_when_eligible(self):
        from src.game.manage_owner_events.public import trigger_random_event

        mock_event_def = MagicMock()
        mock_triggered = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.list_active_owner_events_for_owner",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.game.manage_owner_events.public.get_random_eligible_owner_event_for_owner",
                new_callable=AsyncMock,
                return_value=mock_event_def,
            ),
            patch(
                "src.game.manage_owner_events.public.create_and_execute_event",
                new_callable=AsyncMock,
                return_value=mock_triggered,
            ),
        ):
            result = await trigger_random_event(123, rng=random.Random(42))

        assert result is mock_triggered


# ---------------------------------------------------------------------------
# trigger_specific_event
# ---------------------------------------------------------------------------


class TestTriggerSpecificEvent:
    async def test_returns_none_when_event_not_found(self):
        from src.game.manage_owner_events.public import trigger_specific_event

        with patch(
            "src.game.manage_owner_events.public.db_get_owner_event_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await trigger_specific_event(123, 999)

        assert result is None

    async def test_triggers_event_when_found(self):
        from src.game.manage_owner_events.public import trigger_specific_event

        mock_event_def = MagicMock()
        mock_triggered = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.db_get_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_event_def,
            ),
            patch(
                "src.game.manage_owner_events.public.create_and_execute_event",
                new_callable=AsyncMock,
                return_value=mock_triggered,
            ),
        ):
            result = await trigger_specific_event(123, 10, rng=random.Random(42))

        assert result is mock_triggered

    async def test_passes_inherited_slots(self):
        from src.game.manage_owner_events.public import trigger_specific_event

        mock_event_def = MagicMock()
        mock_triggered = MagicMock()
        slots = {"my_slot": {"pooch_ids": [1]}}

        mock_create = AsyncMock(return_value=mock_triggered)

        with (
            patch(
                "src.game.manage_owner_events.public.db_get_owner_event_by_id",
                new_callable=AsyncMock,
                return_value=mock_event_def,
            ),
            patch(
                "src.game.manage_owner_events.public.create_and_execute_event",
                mock_create,
            ),
        ):
            result = await trigger_specific_event(123, 10, inherited_slots=slots)

        assert result is mock_triggered
        mock_create.assert_awaited_once()
        _, kwargs = mock_create.call_args
        assert kwargs.get("inherited_slots") == slots or mock_create.call_args.args[-1] == slots


# ---------------------------------------------------------------------------
# trigger_event_by_name
# ---------------------------------------------------------------------------


class TestTriggerEventByName:
    async def test_returns_none_when_event_not_found(self):
        from src.game.manage_owner_events.public import trigger_event_by_name

        with patch(
            "src.game.manage_owner_events.public.db_get_owner_event_by_name",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await trigger_event_by_name(123, "nonexistent_event")

        assert result is None

    async def test_delegates_to_trigger_specific_event(self):
        from src.game.manage_owner_events.public import trigger_event_by_name

        mock_event_def = MagicMock()
        mock_event_def.id = 42
        mock_triggered = MagicMock()

        with (
            patch(
                "src.game.manage_owner_events.public.db_get_owner_event_by_name",
                new_callable=AsyncMock,
                return_value=mock_event_def,
            ),
            patch(
                "src.game.manage_owner_events.public.trigger_specific_event",
                new_callable=AsyncMock,
                return_value=mock_triggered,
            ) as mock_trigger,
        ):
            result = await trigger_event_by_name(123, "some_event")

        assert result is mock_triggered
        mock_trigger.assert_awaited_once_with(123, 42, None)
