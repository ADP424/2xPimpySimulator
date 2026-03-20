"""Tests for src/database/utils/randomization.py."""

import random

from src.database.utils.randomization import weighted_choice

# ---------------------------------------------------------------------------
# weighted_choice
# ---------------------------------------------------------------------------


def test_weighted_choice_returns_none_for_empty():
    """weighted_choice should return None when items list is empty."""
    rng = random.Random(42)
    result = weighted_choice(rng, [])
    assert result is None


def test_weighted_choice_single_item():
    """weighted_choice with a single item should always return it."""
    rng = random.Random(0)
    result = weighted_choice(rng, [("only", 1)])
    assert result == "only"


def test_weighted_choice_heavily_weighted():
    """An item with much higher weight should be returned almost always."""
    rng = random.Random(42)
    items = [("a", 1), ("b", 1), ("c", 100)]
    result = weighted_choice(rng, items)
    # With weight 100 for "c" vs 1 for others, overwhelmingly likely to be "c"
    assert result == "c"


def test_weighted_choice_deterministic_with_seed():
    """Same seed should produce the same result."""
    items = [("alpha", 10), ("beta", 10), ("gamma", 10)]

    result1 = weighted_choice(random.Random(99), items)
    result2 = weighted_choice(random.Random(99), items)
    assert result1 == result2


def test_weighted_choice_respects_weights_distribution():
    """Over many trials, items with higher weight should appear more often."""
    rng = random.Random(123)
    items = [("rare", 1), ("common", 99)]
    counts = {"rare": 0, "common": 0}

    for _ in range(1000):
        result = weighted_choice(rng, items)
        if result is not None:
            counts[result] += 1

    # "common" should appear much more frequently
    assert counts["common"] > counts["rare"] * 5


def test_weighted_choice_with_zero_weight():
    """Items with zero weight should effectively never be selected."""
    rng = random.Random(42)
    items = [("zero", 0), ("nonzero", 100)]

    for _ in range(100):
        result = weighted_choice(rng, items)
        assert result == "nonzero"


def test_weighted_choice_with_objects():
    """weighted_choice should work with arbitrary objects, not just strings."""

    class FakeBreed:
        def __init__(self, id, name):
            self.id = id
            self.name = name

    breed_a = FakeBreed(1, "Poodle")
    breed_b = FakeBreed(2, "Labrador")

    rng = random.Random(42)
    items = [(breed_a, 1), (breed_b, 100)]
    result = weighted_choice(rng, items)
    assert result is breed_b
