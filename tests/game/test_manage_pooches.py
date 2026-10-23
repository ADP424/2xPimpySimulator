"""Tests for src/game/manage_pooches.py — get, rename, hourly cooldown tick."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game import (
    get_pooch_by_id,
    rename_pooch,
    run_hourly_breeding_cooldown_check,
)
from src.game.exceptions import PoochNotFound
from tests.conftest import make_pooch

# ---------------------------------------------------------------------------
# get_pooch_by_id
# ---------------------------------------------------------------------------


class TestGetPoochById:
    @patch("src.game.manage_pooches.to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_returns_pooch(self, mock_db_get, mock_to_pooch):
        db_pooch = make_pooch(pooch_id=1, name="Buddy")
        mock_db_get.return_value = db_pooch
        mock_to_pooch.return_value = SimpleNamespace(id=1, name="Buddy")

        result = await get_pooch_by_id(1)
        assert result.name == "Buddy"

    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_not_found_raises(self, mock_db_get):
        mock_db_get.return_value = None
        with pytest.raises(PoochNotFound):
            await get_pooch_by_id(999)


# ---------------------------------------------------------------------------
# rename_pooch
# ---------------------------------------------------------------------------


class TestRenamePooch:
    @patch("src.game.manage_pooches.db_rename_pooch", new_callable=AsyncMock)
    async def test_rename_success(self, mock_rename):
        mock_rename.return_value = make_pooch(pooch_id=1, name="NewName")

        result = await rename_pooch(1, "NewName")
        assert result is True
        mock_rename.assert_awaited_once_with(1, "NewName")

    async def test_name_too_long(self):
        # MAX_NAME_LENGTH = 100
        result = await rename_pooch(1, "A" * 101)
        assert result is False

    @patch("src.game.manage_pooches.db_rename_pooch", new_callable=AsyncMock)
    async def test_name_is_stripped(self, mock_rename):
        mock_rename.return_value = make_pooch(pooch_id=1, name="Trimmed")

        result = await rename_pooch(1, "  Trimmed  ")
        assert result is True
        mock_rename.assert_awaited_once_with(1, "Trimmed")

    @patch("src.game.manage_pooches.db_rename_pooch", new_callable=AsyncMock)
    async def test_pooch_not_found_raises(self, mock_rename):
        mock_rename.return_value = None
        with pytest.raises(PoochNotFound):
            await rename_pooch(999, "ValidName")

    async def test_name_exactly_max_length(self):
        """A name of exactly MAX_NAME_LENGTH (100) should be accepted."""
        with patch("src.game.manage_pooches.db_rename_pooch", new_callable=AsyncMock) as mock_rename:
            mock_rename.return_value = make_pooch(pooch_id=1)
            result = await rename_pooch(1, "A" * 100)
            assert result is True

    async def test_empty_name_allowed(self):
        """An empty string (after strip) is technically valid (len 0 < 100)."""
        with patch("src.game.manage_pooches.db_rename_pooch", new_callable=AsyncMock) as mock_rename:
            mock_rename.return_value = make_pooch(pooch_id=1)
            result = await rename_pooch(1, "   ")
            assert result is True
            mock_rename.assert_awaited_once_with(1, "")


# ---------------------------------------------------------------------------
# run_hourly_breeding_cooldown_check
# ---------------------------------------------------------------------------


class TestRunHourlyBreedingCooldownCheck:
    async def _run(self, fertility_by_pooch, rolls):
        rng_values = iter(rolls)
        with (
            patch(
                "src.game.manage_pooches.list_pooch_ids_on_breeding_cooldown",
                new=AsyncMock(return_value=list(fertility_by_pooch)),
            ),
            patch(
                "src.game.manage_pooches.get_effective_stat",
                new=AsyncMock(side_effect=lambda pid, stat: fertility_by_pooch[pid]),
            ),
            patch("src.game.manage_pooches.decrement_pooch_breeding_cooldown", new=AsyncMock()) as decrement,
            patch("random.Random.random", new=lambda self: next(rng_values)),
        ):
            count = await run_hourly_breeding_cooldown_check(rng_seed=1)
        return count, decrement

    async def test_rolls_effective_fertility_over_divisor(self):
        # fertility 12 / 25 = 0.48 chance: a 0.4 roll succeeds, a 0.6 roll fails
        count, decrement = await self._run({1: 12, 2: 12}, rolls=[0.4, 0.6])
        assert count == 1
        decrement.assert_awaited_once_with(1)

    async def test_immortal_pooches_never_come_back_into_heat(self):
        count, decrement = await self._run({1: 0}, rolls=[0.0])
        assert count == 0
        decrement.assert_not_awaited()
