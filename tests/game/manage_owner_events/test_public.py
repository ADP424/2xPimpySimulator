"""Tests for src/game/manage_owner_events/public.py."""

from unittest.mock import AsyncMock, MagicMock, patch


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
