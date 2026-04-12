"""Tests for src/database/utils/randomization.py."""

import random

from src.database.utils import rarity_choice, weighted_choice
from src.database.utils.randomization import RARITY_WEIGHTS

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


# ---------------------------------------------------------------------------
# rarity_choice
# ---------------------------------------------------------------------------


def test_rarity_choice_returns_none_for_empty():
    """rarity_choice should return None when items list is empty."""
    rng = random.Random(42)
    assert rarity_choice(rng, []) is None


def test_rarity_choice_single_item():
    """rarity_choice with a single item should always return it."""
    rng = random.Random(0)
    result = rarity_choice(rng, [("only", "common")])
    assert result == "only"


def test_rarity_choice_single_rarity_picks_uniformly():
    """When all items share the same rarity, each should appear roughly equally."""
    rng = random.Random(7)
    items = [("a", "common"), ("b", "common"), ("c", "common")]
    counts = {"a": 0, "b": 0, "c": 0}
    for _ in range(900):
        result = rarity_choice(rng, items)
        if result is not None:
            counts[result] += 1
    # Each should appear roughly 300 times; allow ±50% slack
    for count in counts.values():
        assert 150 <= count <= 450


def test_rarity_choice_prefers_common_over_unique():
    """Over many trials, common items should appear far more often than unique ones."""
    rng = random.Random(123)
    items = [("c", "common"), ("u", "unique")]
    counts = {"c": 0, "u": 0}
    for _ in range(1000):
        result = rarity_choice(rng, items)
        if result is not None:
            counts[result] += 1
    # common weight=1000, unique weight=1 → common should dominate
    assert counts["c"] > counts["u"] * 5


def test_rarity_choice_rolls_rarity_first_then_item():
    """With many items at common and one at unique, the unique should still appear
    at roughly the rarity-weight probability (not diluted by item count)."""
    rng = random.Random(99)
    # 100 common items and 1 unique item
    common_items = [(f"c{i}", "common") for i in range(100)]
    unique_item = [("u", "unique")]
    items = common_items + unique_item
    counts = {"common": 0, "unique": 0}
    for _ in range(10000):
        result = rarity_choice(rng, items)
        if result == "u":
            counts["unique"] += 1
        elif result is not None:
            counts["common"] += 1
    # unique weight=1, common weight=1000 → unique should appear ~1/1001 of the time
    # With 10000 trials, expect ~10 unique hits; assert at least 1 and no more than 100
    assert 1 <= counts["unique"] <= 100


def test_rarity_choice_ignores_unknown_rarity():
    """Items with a rarity string not in RARITY_WEIGHTS are silently excluded."""
    rng = random.Random(5)
    items = [("known", "common"), ("unknown", "legendary")]
    for _ in range(50):
        result = rarity_choice(rng, items)
        assert result == "known"


def test_rarity_choice_deterministic_with_seed():
    """Same seed should produce the same result."""
    items = [("x", "rare"), ("y", "rare"), ("z", "uncommon")]
    result1 = rarity_choice(random.Random(77), items)
    result2 = rarity_choice(random.Random(77), items)
    assert result1 == result2


def test_rarity_weights_constant_has_all_rarities():
    """RARITY_WEIGHTS should cover all 8 rarity levels."""
    expected = {"common", "uncommon", "novel", "rare", "unprecedented", "remarkable", "extraordinary", "unique"}
    assert set(RARITY_WEIGHTS.keys()) == expected
