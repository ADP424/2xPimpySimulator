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
