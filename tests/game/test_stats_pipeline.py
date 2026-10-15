"""Tests for src/game/manage_stats.py — the single effective-stat and health calculation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game.constants import REJUVENATION_FERTILITY_MULT
from src.game.manage_stats import (
    compute_effective_stats,
    effective_size,
    get_effective_stat,
    get_pooch_health,
)
from tests.conftest import make_breed, make_mutation, make_pooch


class TestEffectiveSize:
    def test_male_no_change(self):
        p = make_pooch(sex="male", size=10)
        assert effective_size(p) == 10

    def test_female_minus_one(self):
        p = make_pooch(sex="female", size=10)
        assert effective_size(p) == 9

    def test_minimum_clamp(self):
        p = make_pooch(sex="female", size=1)
        assert effective_size(p) == 1

    def test_unknown_sex_treated_as_male(self):
        p = make_pooch(sex="other", size=10)
        assert effective_size(p) == 10


class TestComputeEffectiveStats:
    def test_baseline_no_modifiers(self):
        p = make_pooch()
        stats = compute_effective_stats(p)
        assert stats["strength"] == 10
        assert stats["constitution"] == 10
        assert stats["fertility"] == 10
        assert stats["size"] == 10
        assert stats["base_health"] == 10

    def test_breed_add_applied(self):
        p = make_pooch()
        breed = make_breed(parameters={"strength_add": 3})
        stats = compute_effective_stats(p, breeds=[breed])
        assert stats["strength"] == 13

    def test_breed_mult_applied(self):
        p = make_pooch()
        breed = make_breed(parameters={"fluffiness_mult": 0.5})
        stats = compute_effective_stats(p, breeds=[breed])
        assert stats["fluffiness"] == 5

    def test_mutation_add_and_mult_compose(self):
        p = make_pooch()
        m = make_mutation(parameters={"strength_add": 2, "strength_mult": 0.5})
        stats = compute_effective_stats(p, mutations=[m])
        # (10 + 2) * 0.5 = 6
        assert stats["strength"] == 6

    def test_starvation_reduces_stats(self):
        p = make_pooch(starvation=20)
        stats = compute_effective_stats(p)
        # Affected: strength, fertility, constitution, aggressiveness, base_health
        assert stats["strength"] < 10
        assert stats["fertility"] < 10
        assert stats["constitution"] < 10
        assert stats["aggressiveness"] < 10
        # Cuteness is not on the affected list
        assert stats["cuteness"] == 10

    def test_immortality_zeroes_fertility(self):
        p = make_pooch(immortal=True)
        stats = compute_effective_stats(p)
        assert stats["fertility"] == 0

    def test_rejuvenation_lowers_fertility_and_constitution(self):
        p_normal = make_pooch(rejuvenation_count=0)
        p_rej = make_pooch(rejuvenation_count=3)
        stats_normal = compute_effective_stats(p_normal)
        stats_rej = compute_effective_stats(p_rej)
        assert stats_rej["fertility"] < stats_normal["fertility"]
        assert stats_rej["constitution"] < stats_normal["constitution"]
        # Approx 0.95^3 = 0.857; (10 * 0.857) ~= 8.57 → 9
        assert stats_rej["fertility"] == round(10 * REJUVENATION_FERTILITY_MULT**3)

    def test_female_size_adjustment(self):
        p = make_pooch(sex="female", size=15)
        stats = compute_effective_stats(p)
        assert stats["size"] == 14

    def test_breakdown_returns_sources(self):
        p = make_pooch(sex="female")
        breed = make_breed(parameters={"strength_add": 2})
        breakdown = compute_effective_stats(p, breeds=[breed], return_breakdown=True)
        assert "strength" in breakdown
        assert breakdown["strength"]["base"] == 10
        assert breakdown["strength"]["effective"] == 12
        sources = breakdown["strength"]["sources"]
        assert any(s["source_type"] == "breed" for s in sources)
        # Female adjustment recorded on size.
        assert any(s["source_type"] == "system" for s in breakdown["size"]["sources"])

    def test_negative_clamp(self):
        p = make_pooch()
        # Massive penalty.
        m = make_mutation(parameters={"strength_add": -100})
        stats = compute_effective_stats(p, mutations=[m])
        assert stats["strength"] == 0


def _breed(name, **parameters):
    return SimpleNamespace(name=name, parameters=parameters)


def _catalog(name, id=1, treated=None, **parameters):
    return SimpleNamespace(id=id, name=name, parameters=parameters, treated=treated)


def _instance(kind, catalog, treated=False, visible=True, symptom=None):
    return SimpleNamespace(**{kind: catalog}, treated=treated, visible=visible, displayed_symptom=symptom)


class TestSingleCalculation:
    def test_matches_the_old_database_math(self):
        """Hand-computed with the rules the database used to apply (before lots' new effects)."""
        pooch = make_pooch(strength=10, sex="male")
        mutation = _instance("mutation", _catalog("Brawn", strength_add=2, strength_mult=1.5))
        breeds = [(_breed("Mastiff", strength_add=4, strength_mult=1.2), 3), (_breed("Pug", strength_mult=0.8), 1)]
        injury = _instance("injury", _catalog("Sprain", strength_add=-3))
        disease = _instance("disease", _catalog("Flu", strength_mult=0.5))

        stats = compute_effective_stats(
            pooch, mutations=[mutation], breeds=breeds, injuries=[injury], diseases=[disease]
        )
        # mutations: (10 + 2) * 1.5 = 18
        # breeds:    (18 + 4*0.75) * (1.2*0.75 + 0.8*0.25) = 21 * 1.1 = 23.1
        # injuries:  (23.1 - 3) = 20.1 ; diseases: 20.1 * 0.5 = 10.05 -> 10
        assert stats["strength"] == 10

    def test_treated_parameters_only_once_that_pooch_is_treated(self):
        leg = _catalog("Broken Leg", strength_add=-6, treated={"strength_add": -2})
        untreated = compute_effective_stats(make_pooch(), injuries=[_instance("injury", leg, treated=False)])
        treated = compute_effective_stats(make_pooch(), injuries=[_instance("injury", leg, treated=True)])
        assert (untreated["strength"], treated["strength"]) == (4, 8)

    def test_injury_stacks(self):
        bite = _catalog("Bite", id=5, stacks=[{"min_count": 2, "strength_add": -4}])
        one = compute_effective_stats(make_pooch(), injuries=[_instance("injury", bite)])
        two = compute_effective_stats(make_pooch(), injuries=[_instance("injury", bite), _instance("injury", bite)])
        assert (one["strength"], two["strength"]) == (10, 6)

    def test_lots_effects_now_count(self):
        pooch = make_pooch(sex="female", size=10, starvation=20, rejuvenation_count=1, immortal=True)
        stats = compute_effective_stats(pooch)
        assert stats["size"] == 9
        assert stats["strength"] == 6  # 10 * (1 - 0.02*20)
        assert stats["fertility"] == 0  # immortal pooches are infertile
        assert stats["constitution"] == 6  # 10 * 0.6 (hunger) * 0.95 (rejuvenated) = 5.7

    def test_never_negative_and_size_at_least_one(self):
        stats = compute_effective_stats(make_pooch(size=1), mutations=[_catalog("Tiny", size_add=-5, strength_add=-50)])
        assert stats["strength"] == 0
        assert stats["size"] == 1

    def test_breakdown_lists_sources_with_text(self):
        leg = _instance("injury", _catalog("Broken Leg", strength_add=-3), visible=False, symptom="a limp")
        breakdown = compute_effective_stats(
            make_pooch(),
            injuries=[leg],
            return_breakdown=True,
            label=lambda kind, inst: inst.displayed_symptom if not inst.visible else inst.injury.name,
        )
        assert breakdown["strength"]["base"] == 10
        assert breakdown["strength"]["effective"] == 7
        assert [s["text"] for s in breakdown["strength"]["sources"]] == ["a limp -3"]
        assert breakdown["cuteness"]["sources"] == []


class TestFetchingStats:
    async def test_get_pooch_health(self):
        pooch = make_pooch(base_health=10, starvation=0)
        pooch.health_loss_age = 2
        sources = (pooch, [], [], [], [])
        with (
            patch("src.game.manage_stats.get_pooch_stat_sources", new=AsyncMock(return_value=sources)),
            patch("src.game.manage_stats.get_pooch_health_impact", new=AsyncMock(return_value=-3)),
        ):
            assert await get_pooch_health(1) == 5

    async def test_missing_pooch(self):
        with patch("src.game.manage_stats.get_pooch_stat_sources", new=AsyncMock(return_value=None)):
            assert await get_pooch_health(1) is None
            assert await get_effective_stat(1, "strength") is None


# ===========================================================================
# Modifier math: mutations, breeds (weighted), injuries (treated, stacks), diseases
# (moved from the game Pooch model's old apply_stat_params, which to_pooch no longer uses)
# ===========================================================================


def _effective(base, stat, mutations, breeds, injuries, diseases=()):
    """One effective stat for a male pooch whose ``stat`` is ``base`` and that has the given modifiers."""
    pooch = SimpleNamespace(sex="male", **{stat: base})
    return compute_effective_stats(pooch, mutations=mutations, breeds=breeds, injuries=injuries, diseases=diseases)[
        stat
    ]


def _make_mutation_orm(parameters: dict) -> SimpleNamespace:
    """A minimal mock mutation ORM with a .parameters dict."""
    return SimpleNamespace(parameters=parameters)


def _make_breed_orm(parameters: dict) -> SimpleNamespace:
    """A minimal mock breed ORM with a .parameters dict."""
    return SimpleNamespace(parameters=parameters)


_injury_id_counter = 0


def _make_injury_orm(parameters: dict, injury_id: int = None) -> SimpleNamespace:
    """A minimal mock PoochInjury ORM row with an embedded injury catalog object."""
    global _injury_id_counter
    if injury_id is None:
        _injury_id_counter += 1
        injury_id = _injury_id_counter
    injury_catalog = SimpleNamespace(
        parameters=parameters, name=f"Injury {injury_id}", id=injury_id, treated=parameters.get("treated")
    )
    return SimpleNamespace(injury=injury_catalog, treated=False, displayed_symptom=None, visible=True)


class TestModifierMath:
    def test_no_mutations_no_breeds_returns_base(self):
        assert _effective(10, "strength", [], [], []) == 10

    def test_mutation_add_only(self):
        mut = _make_mutation_orm({"strength_add": 5})
        # (10 + 5) * 1.0 = 15
        assert _effective(10, "strength", [mut], [], []) == 15

    def test_mutation_mult_only(self):
        mut = _make_mutation_orm({"strength_mult": 2.0})
        # (10 + 0) * 2.0 = 20
        assert _effective(10, "strength", [mut], [], []) == 20

    def test_mutation_add_and_mult(self):
        mut = _make_mutation_orm({"strength_add": 5, "strength_mult": 2.0})
        # (10 + 5) * 2.0 = 30
        assert _effective(10, "strength", [mut], [], []) == 30

    def test_multiple_mutations_add_then_mult(self):
        m1 = _make_mutation_orm({"strength_add": 3})
        m2 = _make_mutation_orm({"strength_mult": 1.5})
        # add: 3, mult: 1.0 * 1.5 = 1.5
        # (10 + 3) * 1.5 = 19.5 -> 20 (rounded)
        assert _effective(10, "strength", [m1, m2], [], []) == 20

    def test_multiple_mutations_cumulative_mult(self):
        m1 = _make_mutation_orm({"strength_mult": 2.0})
        m2 = _make_mutation_orm({"strength_mult": 3.0})
        # mult: 2.0 * 3.0 = 6.0, add: 0
        # (10 + 0) * 6.0 = 60
        assert _effective(10, "strength", [m1, m2], [], []) == 60

    def test_breed_add_only_single_breed(self):
        breed = _make_breed_orm({"cuteness_add": 4})
        # After mutation pass: 10
        # Breed: total_weight=1.0, breed_add = 4 * (1/1) = 4, breed_mult = 1.0 * (1/1) = 1.0
        # (10 + 4) * 1.0 = 14
        assert _effective(10, "cuteness", [], [(breed, 1.0)], []) == 14

    def test_breed_mult_only_single_breed(self):
        breed = _make_breed_orm({"cuteness_mult": 1.5})
        # breed_add = 0, breed_mult = 1.5
        # (10 + 0) * 1.5 = 15
        assert _effective(10, "cuteness", [], [(breed, 1.0)], []) == 15

    def test_breed_weighted_average(self):
        b1 = _make_breed_orm({"cuteness_add": 10})
        b2 = _make_breed_orm({"cuteness_add": 0})
        # weights: 3.0 and 1.0, total_weight = 4.0
        # breed_add = 10 * (3/4) + 0 * (1/4) = 7.5
        # breed_mult = 1.0 * (3/4) + 1.0 * (1/4) = 1.0
        # (10 + 7.5) * 1.0 = 17.5 -> 18 (rounded)
        assert _effective(10, "cuteness", [], [(b1, 3.0), (b2, 1.0)], []) == 18

    def test_breed_weighted_mult(self):
        b1 = _make_breed_orm({"strength_mult": 2.0})
        b2 = _make_breed_orm({"strength_mult": 1.0})
        # weights: 1.0 and 1.0, total_weight = 2.0
        # breed_mult = 2.0 * 0.5 + 1.0 * 0.5 = 1.5
        # (10 + 0) * 1.5 = 15
        assert _effective(10, "strength", [], [(b1, 1.0), (b2, 1.0)], []) == 15

    def test_combined_mutations_and_breeds(self):
        mut = _make_mutation_orm({"strength_add": 2, "strength_mult": 1.5})
        breed = _make_breed_orm({"strength_add": 4, "strength_mult": 2.0})
        # Mutation pass: (10 + 2) * 1.5 = 18.0
        # Breed pass: total_weight=1.0, breed_add=4, breed_mult=2.0
        # (18.0 + 4) * 2.0 = 44.0 -> 44
        assert _effective(10, "strength", [mut], [(breed, 1.0)], []) == 44

    def test_zero_base(self):
        mut = _make_mutation_orm({"base_health_add": 5})
        # (0 + 5) * 1.0 = 5
        assert _effective(0, "base_health", [mut], [], []) == 5

    def test_negative_add(self):
        mut = _make_mutation_orm({"dexterity_add": -3})
        # (10 - 3) * 1.0 = 7
        assert _effective(10, "dexterity", [mut], [], []) == 7

    def test_zero_weight_breeds_ignored(self):
        breed = _make_breed_orm({"strength_add": 100})
        # total_weight = 0, so breed branch is skipped entirely
        assert _effective(10, "strength", [], [(breed, 0.0)], []) == 10

    def test_irrelevant_stat_keys_ignored(self):
        mut = _make_mutation_orm({"cuteness_add": 999})
        # Asking for strength -> mutation has no strength keys
        assert _effective(10, "strength", [mut], [], []) == 10

    def test_rounding_half(self):
        mut = _make_mutation_orm({"strength_add": 1})
        # (5 + 1) * 1.0 = 6
        assert _effective(5, "strength", [mut], [], []) == 6

    def test_fractional_rounding(self):
        b1 = _make_breed_orm({"strength_add": 1})
        # breed_add = 1 * (1/3) = 0.333..., breed_mult = 1.0
        # (10 + 0.333) * 1.0 = 10.333 -> 10 (round)
        assert (
            _effective(10, "strength", [], [(b1, 1.0), (_make_breed_orm({}), 1.0), (_make_breed_orm({}), 1.0)], [])
            == 10
        )

    def test_injury_add_only(self):
        inj = _make_injury_orm({"strength_add": -3})
        # mutations pass: (10 + 0) * 1.0 = 10
        # breeds pass: skipped (no breeds)
        # injuries pass: (10 + -3) * 1.0 = 7
        assert _effective(10, "strength", [], [], [inj]) == 7

    def test_injury_mult_only(self):
        inj = _make_injury_orm({"dexterity_mult": 0.5})
        # (10 + 0) * 0.5 = 5
        assert _effective(10, "dexterity", [], [], [inj]) == 5

    def test_injury_add_and_mult(self):
        inj = _make_injury_orm({"strength_add": -2, "strength_mult": 0.5})
        # (10 + -2) * 0.5 = 4
        assert _effective(10, "strength", [], [], [inj]) == 4

    def test_multiple_injuries_cumulative_mult(self):
        i1 = _make_injury_orm({"strength_mult": 0.5})
        i2 = _make_injury_orm({"strength_mult": 0.5})
        # mult: 0.5 * 0.5 = 0.25, add: 0
        # (10 + 0) * 0.25 = 2.5 -> 2 (round)
        assert _effective(10, "strength", [], [], [i1, i2]) == 2

    def test_injuries_applied_after_mutations_and_breeds(self):
        mut = _make_mutation_orm({"strength_add": 5})
        breed = _make_breed_orm({"strength_add": 5})
        inj = _make_injury_orm({"strength_mult": 0.5})
        # mutation pass: (10 + 5) * 1.0 = 15
        # breed pass: (15 + 5) * 1.0 = 20
        # injury pass: (20 + 0) * 0.5 = 10
        assert _effective(10, "strength", [mut], [(breed, 1.0)], [inj]) == 10

    def test_injury_irrelevant_stat_keys_ignored(self):
        inj = _make_injury_orm({"cuteness_add": 999})
        assert _effective(10, "strength", [], [], [inj]) == 10

    def test_stack_fires_at_min_count(self):
        # Two copies of same injury; stack entry requires min_count=2
        stacks = [{"min_count": 2, "strength_add": -5}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # per-instance: (10 + 0) * 1.0 = 10
        # stack (count=2 >= 2): add -5 -> (10 + -5) * 1.0 = 5
        assert _effective(10, "strength", [], [], [inj, inj]) == 5

    def test_stack_does_not_fire_below_min_count(self):
        stacks = [{"min_count": 2, "strength_add": -5}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # count=1 < 2, stack does not fire
        assert _effective(10, "strength", [], [], [inj]) == 10

    def test_stack_max_count_upper_bound(self):
        stacks = [{"min_count": 1, "max_count": 1, "strength_add": -3}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # count=2 > max_count=1, stack does not fire
        assert _effective(10, "strength", [], [], [inj, inj]) == 10

    def test_stack_mult(self):
        stacks = [{"min_count": 2, "dexterity_mult": 0.5}]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # per-instance: 10, stack: (10 + 0) * 0.5 = 5
        assert _effective(10, "dexterity", [], [], [inj, inj]) == 5

    def test_stack_add_and_mult(self):
        stacks = [{"min_count": 2, "dexterity_add": -5, "dexterity_mult": 0.5}]
        inj = _make_injury_orm({"dexterity_add": -1, "stacks": stacks}, injury_id=1)
        # per-instance (x2): add=-2, mult=1.0 -> (10 + -2) * 1.0 = 8
        # stack: (8 + -5) * 0.5 = 1.5 -> 2
        assert _effective(10, "dexterity", [], [], [inj, inj]) == 2

    def test_stacks_independent_per_injury_type(self):
        # Two different injuries each with their own stack; neither fires (count=1 each)
        stacks = [{"min_count": 2, "strength_add": -99}]
        inj_a = _make_injury_orm({"stacks": stacks}, injury_id=10)
        inj_b = _make_injury_orm({"stacks": stacks}, injury_id=11)
        # count per id is 1, threshold is 2 — no stacks fire
        assert _effective(10, "strength", [], [], [inj_a, inj_b]) == 10

    def test_stacks_multiple_entries_both_fire(self):
        stacks = [
            {"min_count": 2, "strength_add": -2},
            {"min_count": 2, "strength_add": -3},
        ]
        inj = _make_injury_orm({"stacks": stacks}, injury_id=1)
        # both entries fire: stack_add = -2 + -3 = -5 -> (10 + -5) * 1.0 = 5
        assert _effective(10, "strength", [], [], [inj, inj]) == 5

    def test_stacks_applied_after_per_instance(self):
        # Stack mult applies to value already modified by per-instance effects
        stacks = [{"min_count": 2, "strength_mult": 2.0}]
        inj = _make_injury_orm({"strength_add": 5, "stacks": stacks}, injury_id=1)
        # per-instance (x2): add=10, mult=1.0 -> (10 + 10) * 1.0 = 20
        # stack: (20 + 0) * 2.0 = 40
        assert _effective(10, "strength", [], [], [inj, inj]) == 40


# ===========================================================================
# Pooch.status
def _make_disease_instance(parameters: dict, visible: bool = True) -> SimpleNamespace:
    """A minimal mock PoochDisease ORM row with an embedded disease catalog object."""
    disease_catalog = SimpleNamespace(parameters=parameters, visible=visible)
    return SimpleNamespace(disease=disease_catalog, visible=visible, displayed_symptom=None)


class TestModifierDiseases:
    def test_disease_add_only(self):
        disease = _make_disease_instance({"strength_add": -3})
        assert _effective(10, "strength", [], [], [], [disease]) == 7

    def test_disease_mult_only(self):
        disease = _make_disease_instance({"constitution_mult": 0.5})
        assert _effective(10, "constitution", [], [], [], [disease]) == 5

    def test_diseases_stack_with_other_modifiers(self):
        mutation = _make_mutation_orm({"strength_add": 2})
        breed = _make_breed_orm({"strength_mult": 1.5})
        injury = _make_injury_orm({"strength_add": -1})
        disease = _make_disease_instance({"strength_mult": 0.5})
        assert _effective(10, "strength", [mutation], [(breed, 1.0)], [injury], [disease]) == 8
