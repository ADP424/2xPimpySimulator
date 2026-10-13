"""Tests for the owner event API routes — what the web may reveal about events and their outcomes."""

from unittest.mock import AsyncMock, patch

from src.game.models.events import (
    OwnerEventEntityReferences,
    OwnerEventOption,
    OwnerEventResult,
    TriggeredOwnerEvent,
)
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext
from src.game.models.events.owner_events.owner_event_entity_reference import (
    OwnerEventEntityReference,
)
from tests.web.conftest import VIEWER_ID


def _event(result=None):
    context = OwnerEventContext(owner_discord_id=VIEWER_ID)
    context.extra_data.update({"_featured_pooch_slot": "target", "target": {"pooch_ids": [3]}})
    context.selected_kennel_id = 9
    refs = OwnerEventEntityReferences()
    refs.pooches.append(OwnerEventEntityReference(id=3, label="Rex"))
    return TriggeredOwnerEvent(
        active_owner_event_id=50,
        event_id=1,
        name="Stray at the Door",
        category="fortune",
        description="A stray appears.",
        flavor_text="",
        severity="moderate",
        requires_response=True,
        response_timeout=60,
        expires_at=None,
        context=context,
        options=[
            OwnerEventOption(
                id=7,
                label="Take it in",
                description="",
                min_money=10,
                min_bloodskulls=0,
                is_default=False,
                is_visible=True,
            )
        ],
        result=result,
        entity_references=refs,
    )


SECRET_RESULT = OwnerEventResult(
    message="",
    money_changed=-10,
    extra_data={
        "selected_outcome": {"message": "It wags its tail.", "chance": 0.37},
        "action_log": [{"type": "money_changes", "amount": -10}],
    },
)


class TestPending:
    def test_serializes_event_without_raw_context(self, client):
        with patch("src.game.get_active_events_for_owner", new=AsyncMock(return_value=[_event()])) as fetch:
            data = client.get("/api/events/pending").get_json()
        fetch.assert_awaited_once_with(VIEWER_ID, pending_only=True)
        event = data[0]
        assert event["id"] == 50
        assert event["featured_pooch"] == {"id": 3, "label": "Rex"}
        assert event["references"]["kennels"] == ["Kennel #9"]
        assert event["options"][0]["min_money"] == 10
        assert "context" not in event and "_featured_pooch_slot" not in repr(event)


class TestRespond:
    def test_success_returns_described_outcome_without_chance(self, client):
        with (
            patch("src.game.get_pending_event", new=AsyncMock(return_value=_event())),
            patch("src.game.respond_to_event", new=AsyncMock(return_value=(True, "", SECRET_RESULT))) as respond,
            patch(
                "src.game.models.events.resolve_owner_event_entity_references",
                new=AsyncMock(return_value=_event().entity_references),
            ),
        ):
            resp = client.post("/api/events/50/respond", json={"option_id": 7})

        respond.assert_awaited_once_with(VIEWER_ID, 50, 7)
        data = resp.get_json()
        assert data["closed"] is True
        assert data["selected_option_label"] == "Take it in"
        assert data["outcome"] == {"headline": "It wags its tail.", "lines": ["Dollars: -10"]}
        body = resp.get_data(as_text=True)
        assert "0.37" not in body and "chance" not in body and "extra_data" not in body

    def test_not_enough_money_keeps_event_open(self, client):
        with (
            patch("src.game.get_pending_event", new=AsyncMock(return_value=_event())),
            patch("src.game.respond_to_event", new=AsyncMock(return_value=(False, "You can't afford that.", None))),
        ):
            data = client.post("/api/events/50/respond", json={"option_id": 7}).get_json()
        assert data["closed"] is False
        assert data["outcome"] is None

    def test_someone_elses_event_is_not_found(self, client):
        respond = AsyncMock()
        with (
            patch("src.game.get_pending_event", new=AsyncMock(return_value=None)),
            patch("src.game.respond_to_event", new=respond),
        ):
            data = client.post("/api/events/50/respond", json={"option_id": 7}).get_json()
        assert data == {"success": False, "message": "Event not found.", "closed": True, "outcome": None}
        respond.assert_not_awaited()

    def test_option_id_required(self, client):
        assert client.post("/api/events/50/respond", json={}).status_code == 400


class TestHistory:
    def test_limit_is_clamped(self, client):
        with patch("src.game.get_event_history", new=AsyncMock(return_value=[])) as history:
            client.get("/api/events/history?limit=500")
        history.assert_awaited_once_with(VIEWER_ID, limit=50)
