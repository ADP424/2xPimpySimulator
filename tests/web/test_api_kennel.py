"""Tests for the breeding, kennel-cleaning and kennel-feeding API routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game import BreedingOutcome
from tests.web.conftest import VIEWER_ID

DAD = SimpleNamespace(id=2, name="Rex")
MOM = SimpleNamespace(id=1, name="Bella")
OTHER = SimpleNamespace(id=3, name="Daisy")


def _outcome(puppy_ids, disease_events=(), female=MOM):
    return BreedingOutcome(list(puppy_ids), list(disease_events), DAD, female, MOM)


def _breed(outcome):
    return patch("src.game.breed_with_mate_choice", new=AsyncMock(return_value=outcome))


class TestBreed:
    def test_twins_without_puppy_ids(self, client):
        with _breed(_outcome([10, 11])) as breed:
            data = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2}).get_json()
        breed.assert_awaited_once_with(VIEWER_ID, 1, 2)
        assert data == {
            "success": True,
            "puppy_count": 2,
            "message": "**Twins!** Rex and Bella are expecting **2** puppies.",
            "disease_lines": [],
            "distracted": False,
        }

    def test_disease_lines(self, client):
        events = [(2, "a mysterious illness", "spread"), (None, "Mange", "inherited")]
        with _breed(_outcome([10], events)):
            data = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2}).get_json()
        assert data["message"] == "**Breeding successful.** Rex and Bella are expecting **1** puppy."
        assert data["disease_lines"] == ["Rex was exposed to a mysterious illness.", "A puppy inherited Mange."]

    def test_distracted(self, client):
        with _breed(_outcome([10], female=OTHER)):
            data = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2}).get_json()
        assert data["distracted"] is True
        assert data["message"].startswith("**Rex got distracted** and ended up mating with **Daisy** instead!")

    def test_breeding_rule_error(self, client):
        error = AsyncMock(side_effect=ValueError("Pooches must be different sexes"))
        with patch("src.game.breed_with_mate_choice", new=error):
            resp = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2})
        assert resp.status_code == 400
        assert resp.get_json() == {"error": "Pooches must be different sexes"}

    def test_someone_elses_pooch_is_refused(self, client):
        breed = AsyncMock()
        with (
            patch("src.game.owns_pooch", new=AsyncMock(side_effect=lambda owner, pid: pid != 2)),
            patch("src.game.breed_with_mate_choice", new=breed),
        ):
            resp = client.post("/api/breed", json={"first_pooch_id": 1, "second_pooch_id": 2})
        assert resp.status_code == 403
        breed.assert_not_awaited()


class TestCleanKennel:
    def test_hand_clean(self, client):
        clean = AsyncMock(return_value=(True, "You tidied up."))
        with patch("src.game.clean_kennel_by_hand", new=clean):
            data = client.post("/api/kennels/5/clean", json={"item_name": "hand"}).get_json()
        clean.assert_awaited_once_with(VIEWER_ID, 5)
        assert data == {"success": True, "message": "You tidied up."}

    def test_item_clean(self, client):
        clean = AsyncMock(return_value=(True, "You used one Soap."))
        with patch("src.game.clean_kennel_with_item", new=clean):
            data = client.post("/api/kennels/5/clean", json={"item_name": "Soap"}).get_json()
        clean.assert_awaited_once_with(VIEWER_ID, 5, "Soap")
        assert data["success"] is True

    def test_requires_item_name(self, client):
        assert client.post("/api/kennels/5/clean", json={}).status_code == 400

    def test_someone_elses_kennel_is_refused(self, client):
        with patch("src.game.owns_kennel", new=AsyncMock(return_value=False)):
            assert client.post("/api/kennels/5/clean", json={"item_name": "hand"}).status_code == 403


class TestFeedKennel:
    def test_passes_viewer_and_returns_stock(self, client):
        feed = AsyncMock(return_value=(True, "Deposited **1x Kibble**.", 12))
        with patch("src.game.feed_kennel", new=feed):
            data = client.post("/api/kennels/5/feed", json={"item_name": "Kibble"}).get_json()
        feed.assert_awaited_once_with(VIEWER_ID, 5, "Kibble", 1)
        assert data == {"success": True, "message": "Deposited **1x Kibble**.", "new_stock": 12}

    def test_failure_is_400(self, client):
        with patch("src.game.feed_kennel", new=AsyncMock(return_value=(False, "That item is not food.", None))):
            resp = client.post("/api/kennels/5/feed", json={"item_name": "Soap"})
        assert resp.status_code == 400
        assert resp.get_json() == {"success": False, "error": "That item is not food."}
