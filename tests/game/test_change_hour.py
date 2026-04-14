"""Tests for src/game/change_hour.py pure helpers + seeded orchestrator paths.

The orchestrator touches many DB functions; most of these tests mock the
database layer and assert that the relevant helpers are invoked with the
expected arguments. Pure helpers (death roll, chance calculators) are
tested directly.
"""

import random
from unittest.mock import AsyncMock, patch

import pytest

from src.game.change_hour import (
    _hourly_fight_chance,
    _miscarriage_chance,
    _stillbirth_chance,
    hourly_death_roll,
)
from src.game.constants import (
    HOURLY_DEATH_CHANCE_PER_HEALTH_UNDER_MIN,
    HOURLY_FIGHT_BASE_CHANCE,
    MIN_HEALTH_FOR_DEATH_CHANCE,
)
from tests.conftest import make_pooch

# ---------------------------------------------------------------------------
# hourly_death_roll
# ---------------------------------------------------------------------------


class TestHourlyDeathRoll:
    def test_healthy_pooch_never_dies(self):
        rng = random.Random(0)
        assert hourly_death_roll(MIN_HEALTH_FOR_DEATH_CHANCE, rng) is False
        assert hourly_death_roll(20, rng) is False

    def test_zero_health_always_dies(self):
        rng = random.Random(0)
        assert hourly_death_roll(0, rng) is True
        assert hourly_death_roll(-1, rng) is True

    def test_immortal_never_dies_above_zero(self):
        rng = random.Random(0)
        assert hourly_death_roll(1, rng, immortal=True) is False
        assert hourly_death_roll(3, rng, immortal=True) is False

    def test_immortal_still_dies_at_zero_health(self):
        rng = random.Random(0)
        assert hourly_death_roll(0, rng, immortal=True) is True

    def test_hourly_rate_is_reasonable(self):
        """For a low-health pooch, repeated hourly rolls give the expected per-hour rate."""
        n = 10_000
        rng = random.Random(42)
        hourly_deaths = sum(hourly_death_roll(2, rng) for _ in range(n))
        # health=2, deficit=3 → chance = 3 * HOURLY_DEATH_CHANCE_PER_HEALTH_UNDER_MIN = 2.4%
        expected = 3 * HOURLY_DEATH_CHANCE_PER_HEALTH_UNDER_MIN
        observed_rate = hourly_deaths / n
        assert abs(observed_rate - expected) < 0.015, f"Hourly death rate off: {observed_rate} vs {expected}"


# ---------------------------------------------------------------------------
# Miscarriage / stillbirth chance calculators
# ---------------------------------------------------------------------------


class TestMiscarriageChance:
    def test_base_rate_young_pooch(self):
        p = make_pooch(age=2, constitution=10, starvation=0)
        assert _miscarriage_chance(p, rng=random.Random(0)) == pytest.approx(0.005, abs=1e-6)

    def test_old_pooch_higher_rate(self):
        young = make_pooch(age=2, constitution=10, starvation=0)
        old = make_pooch(age=10, constitution=10, starvation=0)
        assert _miscarriage_chance(old, rng=random.Random(0)) > _miscarriage_chance(young, rng=random.Random(0))

    def test_low_constitution_higher_rate(self):
        healthy = make_pooch(constitution=20, starvation=0)
        weak = make_pooch(constitution=2, starvation=0)
        assert _miscarriage_chance(weak, rng=random.Random(0)) > _miscarriage_chance(healthy, rng=random.Random(0))

    def test_starving_higher_rate(self):
        full = make_pooch(starvation=0)
        hungry = make_pooch(starvation=20)
        assert _miscarriage_chance(hungry, rng=random.Random(0)) > _miscarriage_chance(full, rng=random.Random(0))


class TestStillbirthChance:
    def test_same_shape_as_miscarriage(self):
        young = make_pooch(age=2, constitution=10, starvation=0)
        assert _stillbirth_chance(young, rng=random.Random(0)) == pytest.approx(0.01, abs=1e-6)  # stillbirth unchanged


# ---------------------------------------------------------------------------
# Fight chance calculator
# ---------------------------------------------------------------------------


class TestHourlyFightChance:
    def test_base_chance_with_average_stats(self):
        p = make_pooch(aggressiveness=10, base_health=10, starvation=0)
        assert _hourly_fight_chance(p) == pytest.approx(HOURLY_FIGHT_BASE_CHANCE, abs=1e-6)

    def test_high_aggressiveness_raises_chance(self):
        p_low = make_pooch(aggressiveness=10)
        p_high = make_pooch(aggressiveness=25)
        assert _hourly_fight_chance(p_high) > _hourly_fight_chance(p_low)

    def test_starving_raises_chance(self):
        p_full = make_pooch(starvation=0)
        p_starv = make_pooch(starvation=50)
        assert _hourly_fight_chance(p_starv) > _hourly_fight_chance(p_full)

    def test_low_health_penalizes(self):
        p_healthy = make_pooch(base_health=10, aggressiveness=15)
        p_dying = make_pooch(base_health=2, aggressiveness=15)
        assert _hourly_fight_chance(p_dying) < _hourly_fight_chance(p_healthy)

    def test_chance_clamped(self):
        """Even with extreme inputs, the chance is bounded to a sane range."""
        p_wild = make_pooch(aggressiveness=10_000, starvation=10_000)
        c = _hourly_fight_chance(p_wild)
        assert 0 <= c <= 0.1


# ---------------------------------------------------------------------------
# Orchestrator smoke — run_hour_change with empty world
# ---------------------------------------------------------------------------


class TestRunHourChangeEmptyWorld:
    async def test_empty_world_returns_empty_summary(self):
        from src.game.change_hour import run_hour_change

        patches = {
            "src.game.change_hour.increment_global_hour": AsyncMock(return_value=1),
            "src.game.change_hour.list_pooch_pregnancies": AsyncMock(return_value=[]),
            "src.game.change_hour.list_living_pooches": AsyncMock(return_value=[]),
            "src.game.change_hour.tick_hourly_breeding_cooldowns": AsyncMock(return_value=0),
            "src.game.change_hour.tick_hourly_injury_persistence": AsyncMock(return_value=0),
            "src.game.change_hour.get_current_season": AsyncMock(return_value="spring"),
            "src.game.change_hour.list_servers": AsyncMock(return_value=[]),
            "src.game.manage_diseases.run_hourly_disease_tick": AsyncMock(return_value={}),
        }
        with (
            patch.multiple(
                "src.game.change_hour",
                **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("src.game.change_hour")},
            ),
            patch(
                "src.game.manage_diseases.run_hourly_disease_tick",
                new=patches["src.game.manage_diseases.run_hourly_disease_tick"],
            ),
        ):
            result = await run_hour_change(rng_seed=42)
        assert result == {}


# ---------------------------------------------------------------------------
# on_death: injure helper
# ---------------------------------------------------------------------------


class TestOnDeathInjureHelper:
    async def test_injure_single_option_guaranteed(self):
        from src.game.models import OtherEvent
        from src.game.utils.on_death_effects import apply_on_death_injure

        source = make_pooch(pooch_id=1, name="Attacker")
        victim = make_pooch(pooch_id=2, name="Victim")
        events: dict[int, list[OtherEvent]] = {}

        fake_injury = type("I", (), {"id": 99, "name": "Minor Scratch"})()
        server = type("S", (), {"discord_id": 100})()

        with (
            patch(
                "src.game.utils.on_death_effects.get_injury_by_name",
                new=AsyncMock(return_value=fake_injury),
            ),
            patch("src.game.utils.on_death_effects.add_injury_to_pooch", new=AsyncMock()) as add_injury,
            patch(
                "src.game.utils.on_death_effects.list_servers_for_pooch",
                new=AsyncMock(return_value=[server]),
            ),
            patch(
                "src.game.utils.on_death_effects.to_pooch",
                new=AsyncMock(side_effect=lambda p: p),
            ),
            patch(
                "src.game.utils.on_death_effects.to_server",
                new=AsyncMock(side_effect=lambda s: s),
            ),
        ):
            await apply_on_death_injure(
                trigger={"on_death_options": ["Minor Scratch"]},
                source_pooch=source,
                target_pooches=[victim],
                other_events_by_server=events,
                rng=random.Random(0),
            )

        add_injury.assert_awaited_once_with(victim.id, fake_injury.id)
        assert events[100][0].message.startswith("Victim") or "Attacker" in events[100][0].message

    async def test_injure_empty_options_no_op(self):
        from src.game.utils.on_death_effects import apply_on_death_injure

        source = make_pooch(pooch_id=1)
        victim = make_pooch(pooch_id=2)
        events: dict = {}
        with patch("src.game.utils.on_death_effects.add_injury_to_pooch", new=AsyncMock()) as add_injury:
            await apply_on_death_injure(
                trigger={"on_death_options": []},
                source_pooch=source,
                target_pooches=[victim],
                other_events_by_server=events,
                rng=random.Random(0),
            )
        add_injury.assert_not_called()
