"""Tests for the breeding and kennel-cleaning API routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests.web.conftest import VIEWER_ID

MOM = SimpleNamespace(id=1, name="Bella")
DAD = SimpleNamespace(id=2, name="Rex")


def _breed(puppy_ids, disease_events=()):
    return (
        patch("src.game.breed_pooches", new=AsyncMock(return_value=(puppy_ids, list(disease_events)))),
        patch("src.game.get_pooch_by_id", new=AsyncMock(side_effect=lambda pid: {1: MOM, 2: DAD}[pid])),
    )


class TestBreed:
    def test_twins_without_puppy_ids(self, client):
        breed, lookup = _breed([10, 11])
        with breed, lookup:
            data = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2}).get_json()
        assert data == {
            "success": True,
            "puppy_count": 2,
            "message": "**Twins!** Bella and Rex are expecting **2** puppies.",
            "disease_lines": [],
        }

    def test_disease_lines(self, client):
        events = [(2, "a mysterious illness", "spread"), (None, "Mange", "inherited")]
        breed, lookup = _breed([10], events)
        with breed, lookup:
            data = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2}).get_json()
        assert data["message"] == "**Breeding successful.** Bella and Rex are expecting **1** puppy."
        assert data["disease_lines"] == ["Rex was exposed to a mysterious illness.", "A puppy inherited Mange."]

    def test_breeding_rule_error(self, client):
        with patch("src.game.breed_pooches", new=AsyncMock(side_effect=ValueError("Pooches must be different sexes"))):
            resp = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2})
        assert resp.status_code == 400
        assert resp.get_json() == {"error": "Pooches must be different sexes"}


class TestCleanKennel:
    def test_passes_viewer(self, client):
        clean = AsyncMock(return_value=(True, "Kennel cleaned!"))
        with patch("src.game.clean_kennel", new=clean):
            data = client.post("/api/kennels/5/clean").get_json()
        clean.assert_awaited_once_with(VIEWER_ID, 5)
        assert data == {"success": True, "message": "Kennel cleaned!"}
