"""Tests for the new Section 7 breeding helpers (chance, mate selection, neuter)."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.breeding import (
    compute_breeding_chance,
    neuter_pooch,
    select_actual_mate,
)


class TestComputeBreedingChance:
    def test_average_intelligence_50_percent(self):
        assert compute_breeding_chance(10) == pytest.approx(0.5)

    def test_low_intelligence_clamped(self):
        assert compute_breeding_chance(0) == 0.1
        assert compute_breeding_chance(-50) == 0.1

    def test_high_intelligence_clamped(self):
        assert compute_breeding_chance(100) == 0.95
        assert compute_breeding_chance(20) == 0.95

    def test_scales_linearly(self):
        # 5 / 20 = 0.25
        assert compute_breeding_chance(5) == pytest.approx(0.25)
        # 15 / 20 = 0.75
        assert compute_breeding_chance(15) == pytest.approx(0.75)


def _female(pooch_id: int):
    return SimpleNamespace(id=pooch_id, sex="female")


class TestSelectActualMate:
    async def test_single_female_always_chosen(self):
        male = SimpleNamespace(id=1, intelligence=2)  # very low → low chance
        intended = _female(10)
        # Only one option → guaranteed.
        result = await select_actual_mate(male, intended, [intended], rng=random.Random(0))
        assert result.id == intended.id

    async def test_high_intelligence_picks_intended(self):
        male = SimpleNamespace(id=1, intelligence=20)  # max chance
        intended = _female(10)
        other = _female(11)
        # 95% chance, but use a seed where the first random < 0.95.
        rng = random.Random(0)
        result = await select_actual_mate(male, intended, [intended, other], rng=rng)
        assert result.id == intended.id

    async def test_low_intelligence_can_pick_other(self):
        male = SimpleNamespace(id=1, intelligence=0)  # 10% chance only
        intended = _female(10)
        other = _female(11)
        # Most rolls should fail and pick "other".
        results = []
        for seed in range(20):
            rng = random.Random(seed)
            result = await select_actual_mate(male, intended, [intended, other], rng=rng)
            results.append(result.id)
        assert other.id in results, "Low-intelligence male should sometimes pick other female"


class TestNeuterPooch:
    async def test_rejects_unknown_pooch(self):
        with patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=None)):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "doesn't exist" in msg

    async def test_rejects_non_owner(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=999)
        with patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "don't own" in msg

    async def test_rejects_dead_pooch(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=False, owner_discord_id=100)
        with patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "dead" in msg

    async def test_rejects_already_neutered(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=100)
        existing = [SimpleNamespace(name="Neutered")]
        with (
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.breeding.list_pooch_injuries", new=AsyncMock(return_value=existing)),
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "already neutered" in msg

    async def test_success_applies_injury(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=100)
        injury = SimpleNamespace(id=42, name="Neutered")
        with (
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.breeding.list_pooch_injuries", new=AsyncMock(return_value=[])),
            patch("src.database.get_injury_by_name", new=AsyncMock(return_value=injury)),
            patch("src.database.add_injury_to_pooch", new=AsyncMock()) as add_inj,
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is True
        add_inj.assert_awaited_once_with(1, 42)
