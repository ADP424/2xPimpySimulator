"""Tests for the server event API routes — menus, availability and what options reveal."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.game.models.events import TriggeredServerEvent
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext
from src.game.models.events.owner_events.owner_event_entity_reference import (
    OwnerEventEntityReference,
    OwnerEventEntityReferences,
)
from src.game.models.events.owner_events.owner_event_result import OwnerEventResult
from src.game.models.events.server_events.server_event_context import ServerEventContext
from src.game.models.events.server_events.server_event_option import (
    ServerEventMenu,
    ServerEventMenuOption,
)
from src.game.models.events.server_events.server_event_participation import (
    ServerEventParticipationSummary,
)
from tests.web.conftest import SERVER_ID, VIEWER_ID


def _option(option_id, label, requires=None):
    return ServerEventMenuOption(
        id=option_id,
        label=label,
        description="",
        filter={"min_age": 3},
        requires=requires or {},
        scoring={"strength": 2.5},
    )


def _event(participation=None):
    menus = [
        ServerEventMenu(
            id=1,
            name="enter",
            label="Enter",
            description="",
            max_uses_per_player=1,
            options=[_option(10, "Enter a pooch", {"pooch": {"filter": {"min_age": 3}}})],
        ),
        ServerEventMenu(
            id=2,
            name="cheer",
            label="Cheer",
            description="",
            max_uses_per_player=-1,
            depends_on=["enter"],
            options=[_option(20, "Cheer loudly")],
        ),
    ]
    return TriggeredServerEvent(
        occurrence_id=99,
        event_id=1,
        server_discord_id=SERVER_ID,
        name="Dog Show",
        category="contest",
        description="Show off.",
        flavor_text="",
        severity="major",
        expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        context=ServerEventContext(server_discord_id=SERVER_ID),
        menus=menus,
        participation_count=4,
        viewer_participation=participation,
    )


def _participation():
    refs = OwnerEventEntityReferences()
    refs.pooches.append(OwnerEventEntityReference(id=3, label="Rex"))
    return ServerEventParticipationSummary(
        owner_discord_id=VIEWER_ID,
        context=OwnerEventContext(owner_discord_id=VIEWER_ID),
        submissions=[
            {
                "menu_name": "enter",
                "option_label": "Enter a pooch",
                "selected_pooch_id": 3,
                "immediate_result": {"message": "Rex struts in.", "extra_data": {"chance": 0.4}},
                "score": 17.5,
            }
        ],
        rank=2,
        resolution_result=OwnerEventResult(message="You placed second!"),
        entity_references=refs,
    )


class TestGetServerEvent:
    def test_no_active_event(self, client):
        with patch("src.game.get_active_server_event", new=AsyncMock(return_value=None)):
            assert client.get("/api/server-event").get_json() == {"event": None}

    def test_menus_before_participating(self, client):
        with patch("src.game.get_active_server_event", new=AsyncMock(return_value=_event())) as fetch:
            resp = client.get("/api/server-event")
        fetch.assert_awaited_once_with(SERVER_ID, viewer_owner_discord_id=VIEWER_ID)
        event = resp.get_json()["event"]
        enter, cheer = event["menus"]
        assert (enter["available"], enter["uses_left"]) == (True, 1)
        assert (cheer["available"], cheer["uses_left"]) == (False, None)
        assert enter["options"][0] == {"id": 10, "label": "Enter a pooch", "description": "", "requires_pooch": True}
        assert event["viewer"]["participated"] is False
        body = resp.get_data(as_text=True)
        for secret in ("min_age", "scoring", "strength", "filter"):
            assert secret not in body

    def test_after_participating(self, client):
        with patch("src.game.get_active_server_event", new=AsyncMock(return_value=_event(_participation()))):
            resp = client.get("/api/server-event")
        event = resp.get_json()["event"]
        enter, cheer = event["menus"]
        assert (enter["available"], enter["uses_left"]) == (False, 0)
        assert cheer["available"] is True
        assert event["viewer"] == {
            "participated": True,
            "submissions": [
                {
                    "menu_name": "enter",
                    "option_label": "Enter a pooch",
                    "pooch_label": "Rex",
                    "message": "Rex struts in.",
                }
            ],
            "rank": 2,
            "resolution_message": "You placed second!",
        }
        assert "17.5" not in resp.get_data(as_text=True) and "0.4" not in resp.get_data(as_text=True)


class TestParticipate:
    def test_passes_viewer_server_and_pooch(self, client):
        participate = AsyncMock(return_value=(False, "That pooch does not belong to you.", None))
        with patch("src.game.participate_in_server_event", new=participate):
            data = client.post("/api/server-event/99/participate", json={"option_id": 10, "pooch_id": 3}).get_json()
        participate.assert_awaited_once_with(99, SERVER_ID, VIEWER_ID, 10, selected_pooch_id=3)
        assert data == {"success": False, "message": "That pooch does not belong to you."}

    def test_rejects_bad_input(self, client):
        url = "/api/server-event/99/participate"
        assert client.post(url, json={}).status_code == 400
        assert client.post(url, json={"option_id": 1, "pooch_id": "3"}).status_code == 400
