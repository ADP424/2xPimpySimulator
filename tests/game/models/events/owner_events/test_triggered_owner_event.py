from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.models.events.owner_events.owner_event_context import OwnerEventContext
from src.game.models.events.owner_events.owner_event_entity_reference import (
    OwnerEventEntityReferences,
)
from src.game.models.events.owner_events.triggered_owner_event import (
    TriggeredOwnerEvent,
    to_triggered_owner_event,
)


class TestTriggeredOwnerEventIsExpired:
    def test_not_expired_when_no_expiry(self):
        event = TriggeredOwnerEvent(
            active_owner_event_id=1,
            event_id=1,
            name="Test",
            category="test",
            description="desc",
            flavor_text="flavor",
            severity="low",
            requires_response=False,
            response_timeout=0,
            expires_at=None,
            context=OwnerEventContext(owner_discord_id=1),
        )
        assert event.is_expired is False

    def test_not_expired_when_future(self):
        event = TriggeredOwnerEvent(
            active_owner_event_id=1,
            event_id=1,
            name="Test",
            category="test",
            description="desc",
            flavor_text="flavor",
            severity="low",
            requires_response=False,
            response_timeout=0,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            context=OwnerEventContext(owner_discord_id=1),
        )
        assert event.is_expired is False

    def test_expired_when_past(self):
        event = TriggeredOwnerEvent(
            active_owner_event_id=1,
            event_id=1,
            name="Test",
            category="test",
            description="desc",
            flavor_text="flavor",
            severity="low",
            requires_response=False,
            response_timeout=0,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            context=OwnerEventContext(owner_discord_id=1),
        )
        assert event.is_expired is True


class TestToTriggeredOwnerEvent:
    def _make_event_occurrence(self, *, requires_response=False, result_summary=None, context_dict=None):
        occ = MagicMock()
        occ.id = 1
        occ.event_id = 10
        occ.expires_at = None
        occ.context = context_dict or {}
        occ.result_summary = result_summary
        return occ

    def _make_event_db(self, *, requires_response=False):
        event = MagicMock()
        event.id = 10
        event.name = "Test Event"
        event.category = "fortune"
        event.description = "A test event"
        event.flavor_text = "Something happened"
        event.severity = "low"
        event.requires_response = requires_response
        event.response_timeout = 3600
        event.options = []
        event.actions = []
        return event

    @pytest.mark.asyncio
    async def test_basic_conversion(self):
        occ = self._make_event_occurrence()
        event_db = self._make_event_db()
        with (
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.get_owner_event_by_id",
                new=AsyncMock(return_value=event_db),
            ),
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.resolve_owner_event_entity_references",
                new=AsyncMock(return_value=OwnerEventEntityReferences()),
            ),
        ):
            result = await to_triggered_owner_event(occ)
        assert result.active_owner_event_id == 1
        assert result.event_id == 10
        assert result.name == "Test Event"
        assert result.category == "fortune"
        assert result.requires_response is False
        assert result.options == []

    @pytest.mark.asyncio
    async def test_event_not_found_raises(self):
        occ = self._make_event_occurrence()
        with patch(
            "src.game.models.events.owner_events.triggered_owner_event.get_owner_event_by_id",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="could not be loaded"):
                await to_triggered_owner_event(occ)

    @pytest.mark.asyncio
    async def test_result_summary_parsed(self):
        occ = self._make_event_occurrence(
            result_summary={"success": True, "message": "It worked!", "money_changed": 100}
        )
        event_db = self._make_event_db()
        with (
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.get_owner_event_by_id",
                new=AsyncMock(return_value=event_db),
            ),
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.resolve_owner_event_entity_references",
                new=AsyncMock(return_value=OwnerEventEntityReferences()),
            ),
        ):
            result = await to_triggered_owner_event(occ)
        assert result.result is not None
        assert result.result.success is True
        assert result.result.money_changed == 100

    @pytest.mark.asyncio
    async def test_requires_response_builds_options(self):
        occ = self._make_event_occurrence()
        event_db = self._make_event_db(requires_response=True)
        opt1 = MagicMock()
        opt1.id = 1
        opt1.is_visible = True
        opt1.option_order = 2
        opt2 = MagicMock()
        opt2.id = 2
        opt2.is_visible = True
        opt2.option_order = 1
        opt_hidden = MagicMock()
        opt_hidden.id = 3
        opt_hidden.is_visible = False
        opt_hidden.option_order = 0
        event_db.options = [opt1, opt2, opt_hidden]

        fake_option = MagicMock()
        with (
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.get_owner_event_by_id",
                new=AsyncMock(return_value=event_db),
            ),
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.resolve_owner_event_entity_references",
                new=AsyncMock(return_value=OwnerEventEntityReferences()),
            ),
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.to_owner_event_option",
                new=AsyncMock(return_value=fake_option),
            ) as mock_to_opt,
        ):
            result = await to_triggered_owner_event(occ)
        # Should have 2 visible options, sorted by order (opt2 first, opt1 second)
        assert len(result.options) == 2
        assert mock_to_opt.await_count == 2

    @pytest.mark.asyncio
    async def test_suppressed_option_ids_filtered(self):
        occ = self._make_event_occurrence(context_dict={"extra_data": {"suppressed_option_ids": [2]}})
        event_db = self._make_event_db(requires_response=True)
        opt1 = MagicMock()
        opt1.id = 1
        opt1.is_visible = True
        opt1.option_order = 1
        opt2 = MagicMock()
        opt2.id = 2
        opt2.is_visible = True
        opt2.option_order = 2
        event_db.options = [opt1, opt2]

        fake_option = MagicMock()
        with (
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.get_owner_event_by_id",
                new=AsyncMock(return_value=event_db),
            ),
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.resolve_owner_event_entity_references",
                new=AsyncMock(return_value=OwnerEventEntityReferences()),
            ),
            patch(
                "src.game.models.events.owner_events.triggered_owner_event.to_owner_event_option",
                new=AsyncMock(return_value=fake_option),
            ),
        ):
            result = await to_triggered_owner_event(occ)
        # Option 2 is suppressed, only option 1 remains
        assert len(result.options) == 1
