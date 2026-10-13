"""Tests for the pooch detail, timeline and cast-out API routes."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.game.models import PoochTimelineEntry
from tests.web.conftest import SERVER_ID, VIEWER_ID
from tests.web.test_serializers import _make_pooch


class TestGetPooch:
    def test_owner_flag_true_for_own_pooch(self, client):
        with patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=_make_pooch(owner_discord_id=VIEWER_ID))):
            data = client.get("/api/pooches/1").get_json()
        assert data["viewer_is_owner"] is True

    def test_owner_flag_false_for_someone_elses_pooch(self, client):
        with patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=_make_pooch(owner_discord_id=999))):
            data = client.get("/api/pooches/1").get_json()
        assert data["viewer_is_owner"] is False
        assert "dollars" not in data["owner"]


class TestTimeline:
    def test_serializes_entries(self, client):
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        entries = [
            PoochTimelineEntry(kind="birth", description="Born.", snapshot_at=at),
            PoochTimelineEntry(kind="vet_injuries", description="Checked.", snapshot_at=at, entity_names=["Sprain"]),
        ]
        with patch("src.game.get_pooch_timeline", new=AsyncMock(return_value=entries)):
            data = client.get("/api/pooches/1/timeline").get_json()
        assert [(e["kind"], e["entity_names"]) for e in data] == [("birth", None), ("vet_injuries", ["Sprain"])]
        assert data[0] == {"kind": "birth", "description": "Born.", "snapshot_at": at.isoformat(), "entity_names": None}


class TestCastOut:
    def test_passes_viewer_and_server(self, client):
        cast_out = AsyncMock(return_value=(False, "That's not your pooch."))
        with patch("src.game.cast_out_pooch", new=cast_out):
            data = client.post("/api/pooches/1/cast-out").get_json()
        cast_out.assert_awaited_once_with(VIEWER_ID, 1, SERVER_ID)
        assert data == {"success": False, "message": "That's not your pooch."}
