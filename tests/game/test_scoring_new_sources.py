"""Tests for the new scoring sources added in Section 2A."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.server_events.scoring import compute_submission_score


@pytest.fixture
def rng():
    return random.Random(0)


# ---------------------------------------------------------------------------
# breed_match
# ---------------------------------------------------------------------------


class TestBreedMatchScoring:
    async def test_full_target_breed_full_score(self, rng):
        # Pooch is 100% Poodle.
        breed_weights = [(1, 10)]
        poodle = SimpleNamespace(name="Poodle")
        with (
            patch(
                "src.game.events.server_events.scoring.list_pooch_breed_weights",
                new=AsyncMock(return_value=breed_weights),
            ),
            patch("src.database.get_breed_by_id", new=AsyncMock(return_value=poodle)),
        ):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {"sources": [{"type": "breed_match", "targets": ["Poodle"], "weight": 30.0}]},
                rng,
            )
        assert score == pytest.approx(30.0)

    async def test_no_match_zero_score(self, rng):
        breed_weights = [(1, 10)]
        labrador = SimpleNamespace(name="Labrador")
        with (
            patch(
                "src.game.events.server_events.scoring.list_pooch_breed_weights",
                new=AsyncMock(return_value=breed_weights),
            ),
            patch("src.database.get_breed_by_id", new=AsyncMock(return_value=labrador)),
        ):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {"sources": [{"type": "breed_match", "targets": ["Poodle"], "weight": 30.0}]},
                rng,
            )
        assert score == 0.0

    async def test_partial_breed_partial_score(self, rng):
        breed_weights = [(1, 5), (2, 5)]  # 50/50 split
        breed_lookup = {1: SimpleNamespace(name="Poodle"), 2: SimpleNamespace(name="Other")}
        with (
            patch(
                "src.game.events.server_events.scoring.list_pooch_breed_weights",
                new=AsyncMock(return_value=breed_weights),
            ),
            patch(
                "src.database.get_breed_by_id",
                new=AsyncMock(side_effect=lambda bid: breed_lookup[bid]),
            ),
        ):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {"sources": [{"type": "breed_match", "targets": ["Poodle"], "weight": 20.0}]},
                rng,
            )
        assert score == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# mutation_match
# ---------------------------------------------------------------------------


class TestMutationMatchScoring:
    async def test_required_present_adds_weight(self, rng):
        muts = [SimpleNamespace(name="Long Coat")]
        with patch(
            "src.game.events.server_events.scoring.list_pooch_mutations",
            new=AsyncMock(return_value=muts),
        ):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {"sources": [{"type": "mutation_match", "required": ["Long Coat"], "weight": 10.0}]},
                rng,
            )
        assert score == pytest.approx(10.0)

    async def test_excluded_present_subtracts_weight(self, rng):
        muts = [SimpleNamespace(name="Aggressive Trait")]
        with patch(
            "src.game.events.server_events.scoring.list_pooch_mutations",
            new=AsyncMock(return_value=muts),
        ):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {"sources": [{"type": "mutation_match", "excluded": ["Aggressive Trait"], "weight": 10.0}]},
                rng,
            )
        assert score == pytest.approx(-10.0)

    async def test_neither_required_nor_excluded(self, rng):
        muts = []
        with patch(
            "src.game.events.server_events.scoring.list_pooch_mutations",
            new=AsyncMock(return_value=muts),
        ):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {
                    "sources": [
                        {
                            "type": "mutation_match",
                            "required": ["Long Coat"],
                            "excluded": ["Bad"],
                            "weight": 5.0,
                        }
                    ]
                },
                rng,
            )
        assert score == 0.0


# ---------------------------------------------------------------------------
# stat_target
# ---------------------------------------------------------------------------


class TestStatTargetScoring:
    async def test_perfect_target_max_score_linear(self, rng):
        pooch = SimpleNamespace(intelligence=15)
        with patch("src.game.events.server_events.scoring.db_get_pooch_by_id", new=AsyncMock(return_value=pooch)):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {
                    "sources": [
                        {
                            "type": "stat_target",
                            "stat": "intelligence",
                            "target": 15,
                            "scale": 20.0,
                            "max_distance": 10,
                            "falloff": "linear",
                        }
                    ]
                },
                rng,
            )
        assert score == pytest.approx(20.0)

    async def test_zero_outside_max_distance(self, rng):
        pooch = SimpleNamespace(intelligence=100)
        with patch("src.game.events.server_events.scoring.db_get_pooch_by_id", new=AsyncMock(return_value=pooch)):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {
                    "sources": [
                        {
                            "type": "stat_target",
                            "stat": "intelligence",
                            "target": 15,
                            "scale": 20.0,
                            "max_distance": 10,
                            "falloff": "linear",
                        }
                    ]
                },
                rng,
            )
        assert score == 0.0

    async def test_gaussian_falloff_smooth(self, rng):
        pooch = SimpleNamespace(intelligence=10)
        with patch("src.game.events.server_events.scoring.db_get_pooch_by_id", new=AsyncMock(return_value=pooch)):
            score = await compute_submission_score(
                {"selected_pooch_id": 1},
                {
                    "sources": [
                        {
                            "type": "stat_target",
                            "stat": "intelligence",
                            "target": 15,
                            "scale": 10.0,
                            "max_distance": 10,
                            "falloff": "gaussian",
                        }
                    ]
                },
                rng,
            )
        # exp(-(5/10)^2) ≈ 0.7788
        assert 7.0 < score < 8.0
