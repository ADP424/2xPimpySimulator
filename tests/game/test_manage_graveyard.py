"""Tests for src/game/manage_graveyard.py — graveyard pooch listing."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game import list_graveyard_pooches
from tests.conftest import make_pooch

# ---------------------------------------------------------------------------
# list_graveyard_pooches
# ---------------------------------------------------------------------------


class TestListGraveyardPooches:
    @patch("src.game.manage_graveyard.to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_graveyard.list_graveyard_pooches_for_owner", new_callable=AsyncMock)
    async def test_returns_pooches_with_dates(self, mock_list, mock_to_pooch):
        now = datetime.now(timezone.utc)
        pooch1 = make_pooch(pooch_id=1, name="Ghost", alive=False)
        pooch2 = make_pooch(pooch_id=2, name="Specter", alive=False)
        mock_list.return_value = [(pooch1, now), (pooch2, now)]
        mock_to_pooch.side_effect = lambda p: SimpleNamespace(id=p.id, name=p.name)

        result = await list_graveyard_pooches(100)
        assert len(result) == 2
        assert result[0][0].name == "Ghost"
        assert result[0][1] == now
        assert result[1][0].name == "Specter"

    @patch("src.game.manage_graveyard.list_graveyard_pooches_for_owner", new_callable=AsyncMock)
    async def test_empty_graveyard(self, mock_list):
        mock_list.return_value = []

        result = await list_graveyard_pooches(100)
        assert result == []

    @patch("src.game.manage_graveyard.to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_graveyard.list_graveyard_pooches_for_owner", new_callable=AsyncMock)
    async def test_correct_owner_discord_id_passed(self, mock_list, mock_to_pooch):
        mock_list.return_value = []

        await list_graveyard_pooches(42)
        mock_list.assert_awaited_once_with(42)

    @patch("src.game.manage_graveyard.to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_graveyard.list_graveyard_pooches_for_owner", new_callable=AsyncMock)
    async def test_preserves_burial_timestamps(self, mock_list, mock_to_pooch):
        """Each pooch should keep its individual buried_at timestamp."""
        t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 15, tzinfo=timezone.utc)
        pooch1 = make_pooch(pooch_id=1, alive=False)
        pooch2 = make_pooch(pooch_id=2, alive=False)
        mock_list.return_value = [(pooch1, t1), (pooch2, t2)]
        mock_to_pooch.side_effect = lambda p: SimpleNamespace(id=p.id)

        result = await list_graveyard_pooches(100)
        assert result[0][1] == t1
        assert result[1][1] == t2

    @patch("src.game.manage_graveyard.to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_graveyard.list_graveyard_pooches_for_owner", new_callable=AsyncMock)
    async def test_single_pooch_graveyard(self, mock_list, mock_to_pooch):
        now = datetime.now(timezone.utc)
        pooch = make_pooch(pooch_id=1, name="Casper", alive=False)
        mock_list.return_value = [(pooch, now)]
        mock_to_pooch.return_value = SimpleNamespace(id=1, name="Casper")

        result = await list_graveyard_pooches(100)
        assert len(result) == 1
        assert result[0][0].name == "Casper"


class TestBreedPopulationSurvey:
    async def test_summarises_each_population(self):
        from types import SimpleNamespace

        from src.game.manage_graveyard import breed_population_survey

        mod = "src.game.manage_graveyard"
        rex = SimpleNamespace(id=1, alive=True)
        bella = SimpleNamespace(id=2, alive=True)
        weights = {1: [(10, 3.0), (20, 1.0)], 2: [(20, 1.0)]}
        names = {10: "Poodle", 20: "Pug"}
        with (
            patch(f"{mod}.list_owner_discord_ids_for_server", new=AsyncMock(return_value=[100])),
            patch(f"{mod}.list_kennels_for_owner", new=AsyncMock(return_value=[SimpleNamespace(id=5)])),
            patch(f"{mod}.list_pooches_for_kennel", new=AsyncMock(return_value=[rex, bella])),
            patch(f"{mod}.list_strays_for_server", new=AsyncMock(return_value=[])),
            patch(f"{mod}.list_graveyard_pooches_for_owners", new=AsyncMock(return_value=[])),
            patch(f"{mod}.list_hell_pooches", new=AsyncMock(return_value=[])),
            patch(f"{mod}.list_pooch_breed_weights", new=AsyncMock(side_effect=lambda pid: weights[pid])),
            patch(f"{mod}.get_breed_by_id", new=AsyncMock(side_effect=lambda bid: SimpleNamespace(name=names[bid]))),
        ):
            survey = await breed_population_survey(1)

        # Pug: (0.25 + 1.0) / 2 pooches; Poodle: 0.75 / 2
        assert survey["owned"] == [
            {"breed": "Pug", "weighted_total": 0.625, "dominant_count": 1},
            {"breed": "Poodle", "weighted_total": 0.375, "dominant_count": 1},
        ]
        assert survey["strays"] == survey["graveyard"] == survey["hell"] == []
