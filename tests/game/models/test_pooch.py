from datetime import datetime
from types import SimpleNamespace

import pytest

from src.game.models.pooch import Pooch, PoochBreedInfo, _apply_stat_params

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pooch(**overrides) -> Pooch:
    """Build a Pooch dataclass with sensible defaults, overridable via kwargs."""
    defaults = dict(
        id=1,
        name="Test",
        age=2,
        sex="male",
        base_health=10,
        health_loss_age=0,
        strength=10,
        cuteness=10,
        fluffiness=10,
        intelligence=10,
        dexterity=10,
        fertility=10,
        aggressiveness=10,
        constitution=10,
        breeding_cooldown=0,
        alive=True,
        virgin=True,
        owner_discord_id=None,
        vendor_id=None,
        created_at=None,
        size=10,
        health=10,
        mood=None,
        owner=None,
        vendor=None,
        breeds=[],
        mutations=[],
        injuries=[],
    )
    defaults.update(overrides)
    return Pooch(**defaults)


def _make_mutation_orm(parameters: dict) -> SimpleNamespace:
    """A minimal mock mutation ORM with a .parameters dict."""
    return SimpleNamespace(parameters=parameters)


def _make_breed_orm(parameters: dict) -> SimpleNamespace:
    """A minimal mock breed ORM with a .parameters dict."""
    return SimpleNamespace(parameters=parameters)


_injury_id_counter = 0


def _make_injury_orm(parameters: dict, injury_id: int = None) -> SimpleNamespace:
    """A minimal mock injury ORM with a .parameters dict and unique id."""
    global _injury_id_counter
    if injury_id is None:
        _injury_id_counter += 1
        injury_id = _injury_id_counter
    return SimpleNamespace(parameters=parameters, id=injury_id)


# ===========================================================================
# _apply_stat_params
# ===========================================================================


class TestApplyStatParams:
    def test_no_mutations_no_breeds_returns_base(self):
        assert _apply_stat_params(10, "strength", [], [], []) == 10

    def test_mutation_add_only(self):
        mut = _make_mutation_orm({"strength_add": 5})
        # (10 + 5) * 1.0 = 15
        assert _apply_stat_params(10, "strength", [mut], [], []) == 15

    def test_mutation_mult_only(self):
        mut = _make_mutation_orm({"strength_mult": 2.0})
        # (10 + 0) * 2.0 = 20
        assert _apply_stat_params(10, "strength", [mut], [], []) == 20

    def test_mutation_add_and_mult(self):
        mut = _make_mutation_orm({"strength_add": 5, "strength_mult": 2.0})
        # (10 + 5) * 2.0 = 30
        assert _apply_stat_params(10, "strength", [mut], [], []) == 30

    def test_multiple_mutations_add_then_mult(self):
        m1 = _make_mutation_orm({"strength_add": 3})
        m2 = _make_mutation_orm({"strength_mult": 1.5})
        # add: 3, mult: 1.0 * 1.5 = 1.5
        # (10 + 3) * 1.5 = 19.5 -> 20 (rounded)
        assert _apply_stat_params(10, "strength", [m1, m2], [], []) == 20

    def test_multiple_mutations_cumulative_mult(self):
        m1 = _make_mutation_orm({"strength_mult": 2.0})
        m2 = _make_mutation_orm({"strength_mult": 3.0})
        # mult: 2.0 * 3.0 = 6.0, add: 0
        # (10 + 0) * 6.0 = 60
        assert _apply_stat_params(10, "strength", [m1, m2], [], []) == 60

    def test_breed_add_only_single_breed(self):
        breed = _make_breed_orm({"cuteness_add": 4})
        # After mutation pass: 10
        # Breed: total_weight=1.0, breed_add = 4 * (1/1) = 4, breed_mult = 1.0 * (1/1) = 1.0
        # (10 + 4) * 1.0 = 14
        assert _apply_stat_params(10, "cuteness", [], [(breed, 1.0)], []) == 14

    def test_breed_mult_only_single_breed(self):
        breed = _make_breed_orm({"cuteness_mult": 1.5})
        # breed_add = 0, breed_mult = 1.5
        # (10 + 0) * 1.5 = 15
        assert _apply_stat_params(10, "cuteness", [], [(breed, 1.0)], []) == 15

    def test_breed_weighted_average(self):
        b1 = _make_breed_orm({"cuteness_add": 10})
        b2 = _make_breed_orm({"cuteness_add": 0})
        # weights: 3.0 and 1.0, total_weight = 4.0
        # breed_add = 10 * (3/4) + 0 * (1/4) = 7.5
        # breed_mult = 1.0 * (3/4) + 1.0 * (1/4) = 1.0
        # (10 + 7.5) * 1.0 = 17.5 -> 18 (rounded)
        assert _apply_stat_params(10, "cuteness", [], [(b1, 3.0), (b2, 1.0)], []) == 18

    def test_breed_weighted_mult(self):
        b1 = _make_breed_orm({"strength_mult": 2.0})
        b2 = _make_breed_orm({"strength_mult": 1.0})
        # weights: 1.0 and 1.0, total_weight = 2.0
        # breed_mult = 2.0 * 0.5 + 1.0 * 0.5 = 1.5
        # (10 + 0) * 1.5 = 15
        assert _apply_stat_params(10, "strength", [], [(b1, 1.0), (b2, 1.0)], []) == 15

    def test_combined_mutations_and_breeds(self):
        mut = _make_mutation_orm({"strength_add": 2, "strength_mult": 1.5})
        breed = _make_breed_orm({"strength_add": 4, "strength_mult": 2.0})
        # Mutation pass: (10 + 2) * 1.5 = 18.0
        # Breed pass: total_weight=1.0, breed_add=4, breed_mult=2.0
        # (18.0 + 4) * 2.0 = 44.0 -> 44
        assert _apply_stat_params(10, "strength", [mut], [(breed, 1.0)], []) == 44

    def test_zero_base(self):
        mut = _make_mutation_orm({"health_add": 5})
        # (0 + 5) * 1.0 = 5
        assert _apply_stat_params(0, "health", [mut], [], []) == 5

    def test_negative_add(self):
        mut = _make_mutation_orm({"dexterity_add": -3})
        # (10 - 3) * 1.0 = 7
        assert _apply_stat_params(10, "dexterity", [mut], [], []) == 7

    def test_zero_weight_breeds_ignored(self):
        breed = _make_breed_orm({"strength_add": 100})
        # total_weight = 0, so breed branch is skipped entirely
        assert _apply_stat_params(10, "strength", [], [(breed, 0.0)], []) == 10

    def test_irrelevant_stat_keys_ignored(self):
        mut = _make_mutation_orm({"cuteness_add": 999})
        # Asking for strength -> mutation has no strength keys
        assert _apply_stat_params(10, "strength", [mut], [], []) == 10

    def test_rounding_half(self):
        mut = _make_mutation_orm({"strength_add": 1})
        # (5 + 1) * 1.0 = 6
        assert _apply_stat_params(5, "strength", [mut], [], []) == 6

    def test_fractional_rounding(self):
        b1 = _make_breed_orm({"strength_add": 1})
        # breed_add = 1 * (1/3) = 0.333..., breed_mult = 1.0
        # (10 + 0.333) * 1.0 = 10.333 -> 10 (round)
        assert (
            _apply_stat_params(
                10, "strength", [], [(b1, 1.0), (_make_breed_orm({}), 1.0), (_make_breed_orm({}), 1.0)], []
            )
            == 10
        )

    def test_injury_add_only(self):
        inj = _make_injury_orm({"strength_add": -3})
        # mutations pass: (10 + 0) * 1.0 = 10
        # breeds pass: skipped (no breeds)
        # injuries pass: (10 + -3) * 1.0 = 7
        assert _apply_stat_params(10, "strength", [], [], [inj]) == 7

    def test_injury_mult_only(self):
        inj = _make_injury_orm({"dexterity_mult": 0.5})
        # (10 + 0) * 0.5 = 5
        assert _apply_stat_params(10, "dexterity", [], [], [inj]) == 5

    def test_injury_add_and_mult(self):
        inj = _make_injury_orm({"strength_add": -2, "strength_mult": 0.5})
        # (10 + -2) * 0.5 = 4
        assert _apply_stat_params(10, "strength", [], [], [inj]) == 4

    def test_multiple_injuries_cumulative_mult(self):
        i1 = _make_injury_orm({"strength_mult": 0.5})
        i2 = _make_injury_orm({"strength_mult": 0.5})
        # mult: 0.5 * 0.5 = 0.25, add: 0
        # (10 + 0) * 0.25 = 2.5 -> 2 (round)
        assert _apply_stat_params(10, "strength", [], [], [i1, i2]) == 2

    def test_injuries_applied_after_mutations_and_breeds(self):
        mut = _make_mutation_orm({"strength_add": 5})
        breed = _make_breed_orm({"strength_add": 5})
        inj = _make_injury_orm({"strength_mult": 0.5})
        # mutation pass: (10 + 5) * 1.0 = 15
        # breed pass: (15 + 5) * 1.0 = 20
        # injury pass: (20 + 0) * 0.5 = 10
        assert _apply_stat_params(10, "strength", [mut], [(breed, 1.0)], [inj]) == 10

    def test_injury_irrelevant_stat_keys_ignored(self):
        inj = _make_injury_orm({"cuteness_add": 999})
        assert _apply_stat_params(10, "strength", [], [], [inj]) == 10

    def test_stack_fires_at_min_count(self):
        # Two copies of same injury; stack entry requires min_count=2
        stacks = [{"min_count": 2, "strength_add": -5}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # per-instance: (10 + 0) * 1.0 = 10
        # stack (count=2 >= 2): add -5 -> (10 + -5) * 1.0 = 5
        assert _apply_stat_params(10, "strength", [], [], [inj, inj]) == 5

    def test_stack_does_not_fire_below_min_count(self):
        stacks = [{"min_count": 2, "strength_add": -5}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # count=1 < 2, stack does not fire
        assert _apply_stat_params(10, "strength", [], [], [inj]) == 10

    def test_stack_max_count_upper_bound(self):
        stacks = [{"min_count": 1, "max_count": 1, "strength_add": -3}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # count=2 > max_count=1, stack does not fire
        assert _apply_stat_params(10, "strength", [], [], [inj, inj]) == 10

    def test_stack_mult(self):
        stacks = [{"min_count": 2, "dexterity_mult": 0.5}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # per-instance: 10, stack: (10 + 0) * 0.5 = 5
        assert _apply_stat_params(10, "dexterity", [], [], [inj, inj]) == 5

    def test_stack_add_and_mult(self):
        stacks = [{"min_count": 2, "dexterity_add": -5, "dexterity_mult": 0.5}]
        inj = _make_injury_orm({"dexterity_add": -1, "stacks": stacks}, injury_id=1)
        # per-instance (x2): add=-2, mult=1.0 -> (10 + -2) * 1.0 = 8
        # stack: (8 + -5) * 0.5 = 1.5 -> 2
        assert _apply_stat_params(10, "dexterity", [], [], [inj, inj]) == 2

    def test_stacks_independent_per_injury_type(self):
        # Two different injuries each with their own stack; neither fires (count=1 each)
        stacks = [{"min_count": 2, "strength_add": -99}]
        inj_a = _make_injury_orm({"stacks": stacks}, injury_id=10)
        inj_b = _make_injury_orm({"stacks": stacks}, injury_id=11)
        # count per id is 1, threshold is 2 — no stacks fire
        assert _apply_stat_params(10, "strength", [], [], [inj_a, inj_b]) == 10

    def test_stacks_multiple_entries_both_fire(self):
        stacks = [
            {"min_count": 2, "strength_add": -2},
            {"min_count": 2, "strength_add": -3},
        ]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # both entries fire: stack_add = -2 + -3 = -5 -> (10 + -5) * 1.0 = 5
        assert _apply_stat_params(10, "strength", [], [], [inj, inj]) == 5

    def test_stacks_applied_after_per_instance(self):
        # Stack mult applies to value already modified by per-instance effects
        stacks = [{"min_count": 2, "strength_mult": 2.0}]
        inj = _make_injury_orm({"strength_add": 5, "stacks": stacks}, injury_id=1)
        # per-instance (x2): add=10, mult=1.0 -> (10 + 10) * 1.0 = 20
        # stack: (20 + 0) * 2.0 = 40
        assert _apply_stat_params(10, "strength", [], [], [inj, inj]) == 40


# ===========================================================================
# Pooch.status
# ===========================================================================


class TestPoochStatus:
    def test_dead_pooch(self):
        p = _make_pooch(alive=False, age=2, health=10)
        assert p.status == "dead"

    def test_dead_takes_priority_over_old(self):
        p = _make_pooch(alive=False, age=15, health=10)
        assert p.status == "dead"

    def test_dead_takes_priority_over_sick(self):
        p = _make_pooch(alive=False, age=2, health=1)
        assert p.status == "dead"

    def test_old_pooch(self):
        p = _make_pooch(alive=True, age=12, health=10)
        assert p.status == "old"

    def test_old_pooch_exact_boundary(self):
        p = _make_pooch(alive=True, age=12, health=10)
        assert p.status == "old"

    def test_old_pooch_well_above(self):
        p = _make_pooch(alive=True, age=20, health=10)
        assert p.status == "old"

    def test_old_takes_priority_over_sick(self):
        p = _make_pooch(alive=True, age=15, health=3)
        assert p.status == "old"

    def test_sick_pooch(self):
        p = _make_pooch(alive=True, age=2, health=3)
        assert p.status == "sick"

    def test_sick_exact_boundary(self):
        p = _make_pooch(alive=True, age=2, health=5)
        assert p.status == "sick"

    def test_sick_health_one(self):
        p = _make_pooch(alive=True, age=2, health=1)
        assert p.status == "sick"

    def test_healthy_pooch(self):
        p = _make_pooch(alive=True, age=2, health=10)
        assert p.status == "healthy"

    def test_healthy_just_above_sick(self):
        p = _make_pooch(alive=True, age=2, health=6)
        assert p.status == "healthy"

    def test_healthy_just_below_old(self):
        p = _make_pooch(alive=True, age=11, health=10)
        assert p.status == "healthy"


# ===========================================================================
# Pooch.birthday
# ===========================================================================


class TestPoochBirthday:
    def test_birthday_returns_created_at(self):
        dt = datetime(2025, 1, 15, 12, 0, 0)
        p = _make_pooch(created_at=dt)
        assert p.birthday == dt

    def test_birthday_none_when_created_at_none(self):
        p = _make_pooch(created_at=None)
        assert p.birthday is None


# ===========================================================================
# PoochBreedInfo
# ===========================================================================


class TestPoochBreedInfo:
    def test_creation(self):
        from src.game.models.breed import Breed

        breed = Breed(
            id=1,
            name="Pug",
            alt_name="",
            category="toy",
            description="A small dog",
            rarity="common",
            min_size=1,
            max_size=5,
        )
        info = PoochBreedInfo(breed=breed, relative_weight=0.75)
        assert info.breed.name == "Pug"
        assert info.relative_weight == 0.75

    def test_frozen(self):
        from src.game.models.breed import Breed

        breed = Breed(
            id=1, name="Pug", alt_name="", category="toy", description="", rarity="common", min_size=1, max_size=5
        )
        info = PoochBreedInfo(breed=breed, relative_weight=0.75)
        with pytest.raises(AttributeError):
            info.relative_weight = 1.0  # type: ignore[misc]


# ===========================================================================
# Pooch is frozen
# ===========================================================================


class TestPoochFrozen:
    def test_cannot_mutate(self):
        p = _make_pooch()
        with pytest.raises(AttributeError):
            p.name = "Changed"  # type: ignore[misc]
