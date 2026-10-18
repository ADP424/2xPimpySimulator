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


def _stats(pooch) -> dict[str, int]:
    """Effective stats for a test pooch (its raw stats: no modifiers)."""
    return {
        stat: getattr(pooch, stat) for stat in ("base_health", "aggressiveness", "constitution", "fertility", "size")
    }


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
        assert _miscarriage_chance(p, _stats(p), rng=random.Random(0)) == pytest.approx(0.005, abs=1e-6)

    def test_old_pooch_higher_rate(self):
        young = make_pooch(age=2, constitution=10, starvation=0)
        old = make_pooch(age=10, constitution=10, starvation=0)
        assert _miscarriage_chance(old, _stats(old), rng=random.Random(0)) > _miscarriage_chance(
            young, _stats(young), rng=random.Random(0)
        )

    def test_low_constitution_higher_rate(self):
        healthy = make_pooch(constitution=20, starvation=0)
        weak = make_pooch(constitution=2, starvation=0)
        assert _miscarriage_chance(weak, _stats(weak), rng=random.Random(0)) > _miscarriage_chance(
            healthy, _stats(healthy), rng=random.Random(0)
        )

    def test_starving_higher_rate(self):
        full = make_pooch(starvation=0)
        hungry = make_pooch(starvation=20)
        assert _miscarriage_chance(hungry, _stats(hungry), rng=random.Random(0)) > _miscarriage_chance(
            full, _stats(full), rng=random.Random(0)
        )


class TestStillbirthChance:
    def test_same_shape_as_miscarriage(self):
        young = make_pooch(age=2, constitution=10, starvation=0)
        assert _stillbirth_chance(young, _stats(young), rng=random.Random(0)) == pytest.approx(
            0.01, abs=1e-6
        )  # stillbirth unchanged


# ---------------------------------------------------------------------------
# Fight chance calculator
# ---------------------------------------------------------------------------


class TestHourlyFightChance:
    def test_base_chance_with_average_stats(self):
        p = make_pooch(aggressiveness=10, base_health=10, starvation=0)
        assert _hourly_fight_chance(p, _stats(p)) == pytest.approx(HOURLY_FIGHT_BASE_CHANCE, abs=1e-6)

    def test_high_aggressiveness_raises_chance(self):
        p_low = make_pooch(aggressiveness=10)
        p_high = make_pooch(aggressiveness=25)
        assert _hourly_fight_chance(p_high, _stats(p_high)) > _hourly_fight_chance(p_low, _stats(p_low))

    def test_starving_raises_chance(self):
        p_full = make_pooch(starvation=0)
        p_starv = make_pooch(starvation=50)
        assert _hourly_fight_chance(p_starv, _stats(p_starv)) > _hourly_fight_chance(p_full, _stats(p_full))

    def test_low_health_penalizes(self):
        p_healthy = make_pooch(base_health=10, aggressiveness=15)
        p_dying = make_pooch(base_health=2, aggressiveness=15)
        assert _hourly_fight_chance(p_dying, _stats(p_dying)) < _hourly_fight_chance(p_healthy, _stats(p_healthy))

    def test_chance_clamped(self):
        """Even with extreme inputs, the chance is bounded to a sane range."""
        p_wild = make_pooch(aggressiveness=10_000, starvation=10_000)
        c = _hourly_fight_chance(p_wild, _stats(p_wild))
        assert 0 <= c <= 0.1


# ---------------------------------------------------------------------------
# Orchestrator smoke — run_hour_change with empty world
# ---------------------------------------------------------------------------


class TestRunHourChangeEmptyWorld:
    async def test_empty_world_returns_empty_summary(self):
        from src.game.change_hour import run_hour_change

        mocks = {
            "run_hourly_breeding_cooldown_check": AsyncMock(return_value=0),
            "run_hourly_injury_persistence_check": AsyncMock(return_value=0),
            "run_hourly_disease_tick": AsyncMock(return_value={}),
        }
        with patch.multiple(
            "src.game.change_hour",
            increment_global_hour=AsyncMock(return_value=1),
            list_pooch_pregnancies=AsyncMock(return_value=[]),
            list_living_pooches=AsyncMock(return_value=[]),
            get_current_season=AsyncMock(return_value="spring"),
            list_servers=AsyncMock(return_value=[]),
            **mocks,
        ):
            result = await run_hour_change(rng_seed=42)
        assert result == {}
        # The cooldown and injury ticks go through the game wrappers (and their constants)
        mocks["run_hourly_breeding_cooldown_check"].assert_awaited_once()
        mocks["run_hourly_injury_persistence_check"].assert_awaited_once()
        mocks["run_hourly_disease_tick"].assert_awaited_once()
        assert mocks["run_hourly_disease_tick"].await_args.kwargs["season"] == "spring"

        # Each sub-tick gets its own seed, drawn reproducibly from the hour's seed
        seeds = [
            mocks["run_hourly_breeding_cooldown_check"].await_args.kwargs["rng_seed"],
            mocks["run_hourly_injury_persistence_check"].await_args.kwargs["rng_seed"],
            mocks["run_hourly_disease_tick"].await_args.kwargs["rng_seed"],
        ]
        assert len(set(seeds)) == 3
        assert 42 not in seeds
        hour_rng = random.Random(42)
        assert seeds == [hour_rng.getrandbits(64) for _ in range(3)]


class TestRunHourChangeFights:
    async def test_fight_uses_shared_fight_and_drops_body_parts_to_winner(self):
        from src.game.change_hour import run_hour_change

        attacker = make_pooch(pooch_id=1, name="Brute", owner_discord_id=10, aggressiveness=10_000)
        victim = make_pooch(pooch_id=2, name="Pup", owner_discord_id=20)
        victim.alive = False  # killed in the fight
        attacker.immortal = False
        pooches = {1: attacker, 2: victim}
        kennel = type("K", (), {"id": 5})()
        fight = AsyncMock(return_value={"winner_id": 1, "defender_died": True, "attacker_died": False})

        with (
            patch.multiple(
                "src.game.change_hour",
                increment_global_hour=AsyncMock(return_value=1),
                list_pooch_pregnancies=AsyncMock(return_value=[]),
                list_living_pooches=AsyncMock(return_value=[attacker]),
                hourly_age_step=AsyncMock(),
                run_hourly_breeding_cooldown_check=AsyncMock(return_value=0),
                run_hourly_injury_persistence_check=AsyncMock(return_value=0),
                run_hourly_disease_tick=AsyncMock(return_value={}),
                get_current_season=AsyncMock(return_value="spring"),
                get_pooch_by_id=AsyncMock(side_effect=lambda pid: pooches[pid]),
                get_pooch_kennel=AsyncMock(return_value=kennel),
                list_pooches_for_kennel=AsyncMock(return_value=[attacker, make_pooch(pooch_id=2, name="Pup")]),
                _hourly_food_tick=AsyncMock(),
                _hourly_fight_chance=lambda p, stats: 1.0,
                get_effective_stats=AsyncMock(return_value={}),
                handle_fight_pooches=fight,
                list_servers_for_pooch=AsyncMock(return_value=[]),
                get_pooch_health=AsyncMock(return_value=100),
                hourly_death_roll=lambda *a, **k: False,
                list_servers=AsyncMock(return_value=[]),
            ),
            patch("src.game.change_hour.drop_body_parts", new=AsyncMock()) as drop,
        ):
            await run_hour_change(rng_seed=1)

        fight.assert_awaited_once()
        assert fight.await_args.args[:2] == (1, 2)
        drop.assert_awaited_once()
        assert drop.await_args.args[0] == 10
        assert drop.await_args.args[1].id == victim.id


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


class TestCannibalism:
    def test_only_starving_pooches(self):
        from src.game.change_hour import _cannibalism_chance

        assert _cannibalism_chance(make_pooch(starvation=0)) == 0.0
        assert _cannibalism_chance(make_pooch(starvation=10)) > _cannibalism_chance(make_pooch(starvation=1)) > 0

    async def test_starving_pooch_eats_kennel_mate(self):
        from src.game.change_hour import run_hour_change

        cannibal = make_pooch(pooch_id=1, name="Gnasher", starvation=40, owner_discord_id=10)
        cannibal.immortal = False
        immortal = make_pooch(pooch_id=3, name="Eternal")
        immortal.immortal = True
        victim = make_pooch(pooch_id=2, name="Snack")
        victim.immortal = False
        eaten = make_pooch(pooch_id=2, name="Snack", alive=False)
        pooches = {1: cannibal, 2: victim}
        server = type("S", (), {"discord_id": 100})()
        guilt = type("I", (), {"id": 77})()

        with (
            patch.multiple(
                "src.game.change_hour",
                increment_global_hour=AsyncMock(return_value=1),
                list_pooch_pregnancies=AsyncMock(return_value=[]),
                list_living_pooches=AsyncMock(return_value=[cannibal]),
                hourly_age_step=AsyncMock(),
                run_hourly_breeding_cooldown_check=AsyncMock(return_value=0),
                run_hourly_injury_persistence_check=AsyncMock(return_value=0),
                run_hourly_disease_tick=AsyncMock(return_value={}),
                get_current_season=AsyncMock(return_value="spring"),
                get_pooch_by_id=AsyncMock(side_effect=lambda pid: pooches[pid]),
                get_pooch_kennel=AsyncMock(return_value=type("K", (), {"id": 5})()),
                list_pooches_for_kennel=AsyncMock(return_value=[cannibal, victim, immortal]),
                _hourly_food_tick=AsyncMock(),
                _hourly_fight_chance=lambda p, stats: 0.0,
                get_effective_stats=AsyncMock(return_value={}),
                _cannibalism_chance=lambda p: 1.0,
                _kill_pooch=AsyncMock(return_value=eaten),
                update_pooch_mood=AsyncMock(),
                modify_pooch_starvation=AsyncMock(),
                get_injury_by_name=AsyncMock(return_value=guilt),
                add_injury_to_pooch=AsyncMock(),
                list_servers_for_pooch=AsyncMock(return_value=[server]),
                to_server=AsyncMock(return_value=server),
                to_pooch=AsyncMock(side_effect=lambda p: p),
                get_pooch_health=AsyncMock(return_value=100),
                hourly_death_roll=lambda *a, **k: False,
                list_servers=AsyncMock(return_value=[server]),
            ),
            patch("src.game.change_hour.HourChangeSummary", new=lambda **kw: kw),
        ):
            from src.game import change_hour

            result = await run_hour_change(rng_seed=1)
            change_hour._kill_pooch.assert_awaited_once_with(victim)
            change_hour.modify_pooch_starvation.assert_awaited_once_with(1, -40)
            change_hour.add_injury_to_pooch.assert_awaited_once_with(1, 77)

        deaths = result[100]["deaths"]
        assert [d.message for d in deaths] == ["Snack was eaten by Gnasher, who had been starving."]


class TestOrphanedFetus:
    async def test_fetus_dies_when_mother_is_dead(self):
        from src.game.change_hour import run_hour_change

        mother = make_pooch(pooch_id=1, name="Snomer", alive=False)
        fetus = make_pooch(pooch_id=2, name="Walkingmer", age=-1, owner_discord_id=10)
        dead_fetus = make_pooch(pooch_id=2, name="Walkingmer", age=-1, alive=False, owner_discord_id=10)
        pooches = {1: mother, 2: fetus}
        pregnancy = type("P", (), {"mother_id": 1, "fetus_id": 2})()
        server = type("S", (), {"discord_id": 100})()

        with (
            patch.multiple(
                "src.game.change_hour",
                increment_global_hour=AsyncMock(return_value=1),
                list_pooch_pregnancies=AsyncMock(return_value=[pregnancy]),
                list_living_pooches=AsyncMock(return_value=[]),
                run_hourly_breeding_cooldown_check=AsyncMock(return_value=0),
                run_hourly_injury_persistence_check=AsyncMock(return_value=0),
                run_hourly_disease_tick=AsyncMock(return_value={}),
                get_current_season=AsyncMock(return_value="spring"),
                get_pooch_by_id=AsyncMock(side_effect=lambda pid: pooches[pid]),
                delete_pregnancy=AsyncMock(),
                set_pooch_dead=AsyncMock(return_value=dead_fetus),
                bury_pooch=AsyncMock(),
                decrement_pooch_pregnancy_timer=AsyncMock(),
                list_servers_for_pooch=AsyncMock(return_value=[server]),
                to_server=AsyncMock(return_value=server),
                to_pooch=AsyncMock(side_effect=lambda p: p),
                list_servers=AsyncMock(return_value=[server]),
            ),
            patch("src.game.change_hour.HourChangeSummary", new=lambda **kw: kw),
        ):
            from src.game import change_hour

            result = await run_hour_change(rng_seed=1)
            change_hour.delete_pregnancy.assert_awaited_once_with(1, 2)
            change_hour.set_pooch_dead.assert_awaited_once_with(2)
            change_hour.bury_pooch.assert_awaited_once_with(10, 2)
            change_hour.decrement_pooch_pregnancy_timer.assert_not_awaited()

        deaths = result[100]["deaths"]
        assert [d.message for d in deaths] == ["Walkingmer died unborn along with Snomer."]


class TestHourTickUsesDatabaseRows:
    def test_pooches_come_from_the_database_not_the_game_model(self):
        """The tick reads columns (immortal, starvation, consumption, birth_hour) the game Pooch used to lack."""
        import src.database
        from src.game import change_hour

        assert change_hour.get_pooch_by_id is src.database.get_pooch_by_id

    def test_fight_chance_uses_effective_stats_not_raw(self):
        calm_raw = make_pooch(aggressiveness=10, starvation=0)
        assert _hourly_fight_chance(calm_raw, {"aggressiveness": 30, "base_health": 10}) > _hourly_fight_chance(
            calm_raw, _stats(calm_raw)
        )
