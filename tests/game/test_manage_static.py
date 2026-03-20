"""Tests for src/game/manage_static.py — breed and mutation lookups."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from conftest import make_breed, make_mutation
from src.game.manage_static import (
    get_breed_by_id,
    get_mutation_by_id,
    list_all_breeds,
    list_all_mutations,
)

# ---------------------------------------------------------------------------
# get_breed_by_id
# ---------------------------------------------------------------------------


class TestGetBreedById:
    @patch("src.game.manage_static.to_breed", new_callable=AsyncMock)
    @patch("src.game.manage_static.db_get_breed_by_id", new_callable=AsyncMock)
    async def test_returns_breed(self, mock_db_get, mock_to_breed):
        breed = make_breed(breed_id=1, name="Golden Retriever")
        mock_db_get.return_value = breed
        mock_to_breed.return_value = SimpleNamespace(id=1, name="Golden Retriever")

        result = await get_breed_by_id(1)
        assert result.name == "Golden Retriever"

    @patch("src.game.manage_static.db_get_breed_by_id", new_callable=AsyncMock)
    async def test_returns_none_if_not_found(self, mock_db_get):
        mock_db_get.return_value = None

        result = await get_breed_by_id(999)
        assert result is None

    @patch("src.game.manage_static.to_breed", new_callable=AsyncMock)
    @patch("src.game.manage_static.db_get_breed_by_id", new_callable=AsyncMock)
    async def test_conversion_called(self, mock_db_get, mock_to_breed):
        breed = make_breed(breed_id=5)
        mock_db_get.return_value = breed
        mock_to_breed.return_value = breed

        await get_breed_by_id(5)
        mock_to_breed.assert_awaited_once_with(breed)


# ---------------------------------------------------------------------------
# get_mutation_by_id
# ---------------------------------------------------------------------------


class TestGetMutationById:
    @patch("src.game.manage_static.to_mutation", new_callable=AsyncMock)
    @patch("src.game.manage_static.db_get_mutation_by_id", new_callable=AsyncMock)
    async def test_returns_mutation(self, mock_db_get, mock_to_mutation):
        mutation = make_mutation(mutation_id=1, name="Cataracts")
        mock_db_get.return_value = mutation
        mock_to_mutation.return_value = SimpleNamespace(id=1, name="Cataracts")

        result = await get_mutation_by_id(1)
        assert result.name == "Cataracts"

    @patch("src.game.manage_static.db_get_mutation_by_id", new_callable=AsyncMock)
    async def test_returns_none_if_not_found(self, mock_db_get):
        mock_db_get.return_value = None

        result = await get_mutation_by_id(999)
        assert result is None

    @patch("src.game.manage_static.to_mutation", new_callable=AsyncMock)
    @patch("src.game.manage_static.db_get_mutation_by_id", new_callable=AsyncMock)
    async def test_conversion_called(self, mock_db_get, mock_to_mutation):
        mutation = make_mutation(mutation_id=3)
        mock_db_get.return_value = mutation
        mock_to_mutation.return_value = mutation

        await get_mutation_by_id(3)
        mock_to_mutation.assert_awaited_once_with(mutation)


# ---------------------------------------------------------------------------
# list_all_breeds
# ---------------------------------------------------------------------------


class TestListAllBreeds:
    @patch("src.game.manage_static.to_breed", new_callable=AsyncMock)
    @patch("src.game.manage_static.db_list_all_breeds", new_callable=AsyncMock)
    async def test_returns_all_breeds(self, mock_list, mock_to_breed):
        breeds = [make_breed(breed_id=1), make_breed(breed_id=2), make_breed(breed_id=3)]
        mock_list.return_value = breeds
        mock_to_breed.side_effect = lambda b: b

        result = await list_all_breeds()
        assert len(result) == 3

    @patch("src.game.manage_static.db_list_all_breeds", new_callable=AsyncMock)
    async def test_returns_empty_list(self, mock_list):
        mock_list.return_value = []

        result = await list_all_breeds()
        assert result == []


# ---------------------------------------------------------------------------
# list_all_mutations
# ---------------------------------------------------------------------------


class TestListAllMutations:
    @patch("src.game.manage_static.to_mutation", new_callable=AsyncMock)
    @patch("src.game.manage_static.db_list_all_mutations", new_callable=AsyncMock)
    async def test_returns_all_mutations(self, mock_list, mock_to_mutation):
        mutations = [make_mutation(mutation_id=1), make_mutation(mutation_id=2)]
        mock_list.return_value = mutations
        mock_to_mutation.side_effect = lambda m: m

        result = await list_all_mutations()
        assert len(result) == 2

    @patch("src.game.manage_static.db_list_all_mutations", new_callable=AsyncMock)
    async def test_returns_empty_list(self, mock_list):
        mock_list.return_value = []

        result = await list_all_mutations()
        assert result == []
