"""Tests for the Patient Room API routes in src/web/routes/api.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests.web.conftest import VIEWER_ID


def _pooch(owner_discord_id=VIEWER_ID, **extra):
    defaults = dict(
        id=7,
        name="Rex",
        owner_discord_id=owner_discord_id,
        vet_checked=False,
        injuries=[SimpleNamespace(visible=False)],
        mutations=[SimpleNamespace(visible=False), SimpleNamespace(visible=True)],
        diseases=[SimpleNamespace(visible=False)],
    )
    defaults.update(extra)
    return SimpleNamespace(**defaults)


def _hidden_injury():
    return SimpleNamespace(
        id=11,
        injury_id=3,
        injury=SimpleNamespace(name="Internal Bleeding", severity="major"),
        visible=False,
        displayed_symptom="pale gums",
        persistence=4,
        treated=False,
        last_treated_at=None,
    )


def _hidden_disease():
    return SimpleNamespace(
        id=12,
        disease_id=5,
        disease=SimpleNamespace(name="Secret Plague", treatable=True, curable=False),
        visible=False,
        displayed_symptom="a cough",
        treated=False,
    )


class TestPatientDetail:
    def test_other_players_pooch_is_forbidden(self, client):
        with patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=_pooch(owner_discord_id=999))):
            resp = client.get("/api/pooches/7/patient")
        assert resp.status_code == 403
        assert resp.get_json() == {"error": "That's not your pooch."}

    def test_hidden_conditions_show_symptoms_only(self, client):
        with (
            patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=_pooch())),
            patch("src.game.get_pooch_injury_instances", new=AsyncMock(return_value=[_hidden_injury()])),
            patch("src.game.get_pooch_disease_instances", new=AsyncMock(return_value=[_hidden_disease()])),
        ):
            resp = client.get("/api/pooches/7/patient")

        data = resp.get_json()
        assert resp.status_code == 200
        assert data["injuries"][0]["label"] == "pale gums"
        assert data["injuries"][0]["injury_id"] is None
        assert data["diseases"][0]["label"] == "a cough"
        assert data["diseases"][0]["disease_id"] is None
        assert data["undiagnosed_mutation_count"] == 1
        assert data["undiagnosed_disease_count"] == 1
        assert "Internal Bleeding" not in resp.get_data(as_text=True)
        assert "Secret Plague" not in resp.get_data(as_text=True)


class TestVetActions:
    def test_diagnose_other_players_pooch_charges_nothing(self, client):
        diagnose = AsyncMock()
        with (
            patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=_pooch(owner_discord_id=999))),
            patch("src.game.diagnose_injuries", new=diagnose),
        ):
            resp = client.post("/api/pooches/7/diagnose/injuries")
        assert resp.status_code == 403
        diagnose.assert_not_awaited()

    def test_diagnose_reports_partial_diagnosis(self, client):
        pooch = _pooch(injuries=[SimpleNamespace(visible=False), SimpleNamespace(visible=False)])
        with (
            patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.diagnose_injuries", new=AsyncMock(return_value=(True, "", ["Sprain"]))),
        ):
            data = client.post("/api/pooches/7/diagnose/injuries").get_json()
        assert data == {"success": True, "message": "", "revealed": ["Sprain"], "fully_diagnosed": False}

    def test_unknown_diagnosis_kind(self, client):
        assert client.post("/api/pooches/7/diagnose/vibes").status_code == 404

    def test_medical_exam_keeps_stat_order(self, client):
        report = {"Strength": "Average", "Cuteness": "Above Average", "Size Class": "10"}
        with (
            patch("src.game.get_pooch_by_id", new=AsyncMock(return_value=_pooch())),
            patch("src.game.medical_exam", new=AsyncMock(return_value=(True, "", report))),
        ):
            data = client.post("/api/pooches/7/medical-exam").get_json()
        assert data["report"] == [["Strength", "Average"], ["Cuteness", "Above Average"], ["Size Class", "10"]]

    def test_treat_injury_passes_viewer(self, client):
        treat = AsyncMock(return_value=(False, "That's not your pooch.", 0))
        with patch("src.game.treat_injury", new=treat):
            data = client.post("/api/clinic/injuries/11/treat").get_json()
        treat.assert_awaited_once_with(VIEWER_ID, 11)
        assert data == {"success": False, "message": "That's not your pooch.", "cost": 0}
