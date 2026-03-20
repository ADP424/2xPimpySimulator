"""Tests for src/game/manage_graveyard.py — graveyard pooch listing."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from conftest import make_pooch
from src.game.manage_graveyard import list_graveyard_pooches

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
