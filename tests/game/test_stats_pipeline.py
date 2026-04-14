"""Tests for src/game/stats.py — central effective-stat computation."""

from src.game.constants import REJUVENATION_FERTILITY_MULT
from src.game.manage_stats import compute_effective_stats, effective_size
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
