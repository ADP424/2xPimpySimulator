import random

from src.game.action_helpers.amount import (
    get_amount_from_parameters,
    get_mode,
    resolve_amount,
)


class TestGetAmountFromParameters:
    def test_static_amount(self):
        rng = random.Random(42)
        assert get_amount_from_parameters({"amount": 10}, rng) == 10

    def test_static_amount_zero(self):
        rng = random.Random(42)
        assert get_amount_from_parameters({"amount": 0}, rng) == 0

    def test_static_amount_negative(self):
        rng = random.Random(42)
        assert get_amount_from_parameters({"amount": -5}, rng) == -5

    def test_no_amount_returns_zero(self):
        rng = random.Random(42)
        assert get_amount_from_parameters({}, rng) == 0

    def test_min_max_range(self):
        rng = random.Random(42)
        result = get_amount_from_parameters({"min_amount": 1, "max_amount": 10}, rng)
        assert 1 <= result <= 10

    def test_min_max_single_value(self):
        rng = random.Random(42)
        result = get_amount_from_parameters({"min_amount": 5, "max_amount": 5}, rng)
        assert result == 5

    def test_min_max_with_exclude(self):
        rng = random.Random(42)
        # Range 1-3, exclude 2 -> must be 1 or 3
        result = get_amount_from_parameters({"min_amount": 1, "max_amount": 3, "exclude_amount": [2]}, rng)
        assert result in (1, 3)

    def test_min_max_exclude_all_but_one(self):
        rng = random.Random(42)
        # Range 1-3, exclude 1 and 3 -> must be 2
        result = get_amount_from_parameters({"min_amount": 1, "max_amount": 3, "exclude_amount": [1, 3]}, rng)
        assert result == 2

    def test_min_max_exclude_all_returns_lo(self):
        rng = random.Random(42)
        # Range 1-2, exclude 1 and 2 -> candidates empty, falls back to lo=1
        result = get_amount_from_parameters({"min_amount": 1, "max_amount": 2, "exclude_amount": [1, 2]}, rng)
        assert result == 1

    def test_exclude_non_list_treated_as_empty(self):
        rng = random.Random(42)
        # exclude_amount is not a list -> exclude_set should be empty
        result = get_amount_from_parameters({"min_amount": 5, "max_amount": 5, "exclude_amount": "not_a_list"}, rng)
        assert result == 5

    def test_min_max_consistent_with_seed(self):
        """Same seed produces same result."""
        params = {"min_amount": 1, "max_amount": 100}
        r1 = get_amount_from_parameters(params, random.Random(99))
        r2 = get_amount_from_parameters(params, random.Random(99))
        assert r1 == r2

    def test_min_max_different_seeds_may_differ(self):
        """Different seeds can produce different results (probabilistic but very likely)."""
        params = {"min_amount": 1, "max_amount": 1000}
        results = {get_amount_from_parameters(params, random.Random(i)) for i in range(20)}
        assert len(results) > 1  # at least 2 different values across 20 seeds

    def test_min_max_takes_priority_over_amount(self):
        """If both min_max and amount are present, min_max is used."""
        rng = random.Random(42)
        result = get_amount_from_parameters({"amount": 999, "min_amount": 1, "max_amount": 1}, rng)
        assert result == 1


class TestResolveAmount:
    def test_roll_once_false_default(self):
        rng = random.Random(42)
        amount, rolled = resolve_amount({"amount": 10}, rng)
        assert amount is None
        assert rolled is False

    def test_roll_once_true(self):
        rng = random.Random(42)
        amount, rolled = resolve_amount({"roll_once": True, "amount": 10}, rng)
        assert amount == 10
        assert rolled is True

    def test_roll_once_with_range(self):
        rng = random.Random(42)
        amount, rolled = resolve_amount({"roll_once": True, "min_amount": 1, "max_amount": 100}, rng)
        assert amount is not None
        assert 1 <= amount <= 100
        assert rolled is True

    def test_roll_once_false_explicit(self):
        rng = random.Random(42)
        amount, rolled = resolve_amount({"roll_once": False, "amount": 10}, rng)
        assert amount is None
        assert rolled is False

    def test_roll_once_truthy_values(self):
        rng = random.Random(42)
        amount, rolled = resolve_amount({"roll_once": 1, "amount": 5}, rng)
        assert rolled is True
        assert amount == 5

    def test_no_roll_once_key(self):
        rng = random.Random(42)
        amount, rolled = resolve_amount({"amount": 10}, rng)
        assert amount is None
        assert rolled is False


class TestGetMode:
    def test_default_is_modify(self):
        assert get_mode({}) == "modify"

    def test_explicit_modify(self):
        assert get_mode({"mode": "modify"}) == "modify"

    def test_explicit_set(self):
        assert get_mode({"mode": "set"}) == "set"

    def test_set_case_insensitive(self):
        assert get_mode({"mode": "SET"}) == "set"
        assert get_mode({"mode": "Set"}) == "set"

    def test_set_with_whitespace(self):
        assert get_mode({"mode": " set "}) == "set"

    def test_non_string_mode_returns_modify(self):
        assert get_mode({"mode": 42}) == "modify"
        assert get_mode({"mode": None}) == "modify"
        assert get_mode({"mode": True}) == "modify"

    def test_unrecognized_string_returns_modify(self):
        assert get_mode({"mode": "add"}) == "modify"
        assert get_mode({"mode": "something_else"}) == "modify"
