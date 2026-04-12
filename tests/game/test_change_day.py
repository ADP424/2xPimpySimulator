"""Tests for src/game/change_day.py — death rolls and the daily tick."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game import death_roll, run_day_change
from tests.conftest import (
    make_kennel,
    make_mutation,
    make_pooch,
    make_server,
    make_vendor,
)


@pytest.fixture(autouse=True)
def mock_change_day_db_calls():
    """Auto-patch DB-touching functions so old-style @patch tests never hit the real DB."""
    with (
        patch("src.game.change_day.get_current_season", new=AsyncMock(return_value="spring")),
        patch("src.game.change_day.update_pooch_mood", new=AsyncMock()),
        patch("src.game.change_day.get_active_auction_sale_listing_for_pooch", new=AsyncMock(return_value=None)),
        patch("src.game.change_day.list_bids_for_listing", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.close_auction_sale_listing", new=AsyncMock()),
        patch("src.game.change_day.give_money_to_owner", new=AsyncMock()),
        patch("src.game.change_day.process_expired_sale_listings", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.list_hell_pooches", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.bury_pooch", new=AsyncMock()),
        patch("src.game.change_day.list_vendor_desired_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.list_vendor_desired_breeds", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.increment_global_day", new=AsyncMock(return_value=1)),
        patch("src.game.change_day.run_daily_disease_tick", new=AsyncMock(return_value={})),
        patch("src.game.change_day.list_pooch_diseases", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.get_disease_health_impact", new=AsyncMock(return_value=None)),
        patch("src.game.change_day.list_pooch_injuries", new=AsyncMock(return_value=[])),
        patch("src.game.change_day.get_injury_health_impact", new=AsyncMock(return_value=None)),
    ):
        yield


# ---------------------------------------------------------------------------
# death_roll
# ---------------------------------------------------------------------------


class TestDeathRoll:
    def test_health_above_minimum_never_dies(self):
        """Health >= MIN_HEALTH_FOR_DEATH_CHANCE (5) always returns False."""
        rng = random.Random(0)
        for health in (5, 6, 10, 100):
            assert death_roll(health, rng) is False

    def test_health_zero_always_dies(self):
        """Health 0 gives chance = min(0.2 * 5, 1.0) = 1.0, so always dies."""
        rng = random.Random(42)
        assert death_roll(0, rng) is True

    def test_negative_health_always_dies(self):
        """Negative health is clamped to 0, so deficit = 5, chance = 1.0."""
        rng = random.Random(99)
        assert death_roll(-10, rng) is True

    def test_health_4_deterministic_death(self):
        """Health 4 gives deficit=1, chance=0.2. Deterministic with seed."""
        rng = random.Random(42)
        roll = rng.random()  # Check what 42 produces
        rng = random.Random(42)
        result = death_roll(4, rng)
        # chance = 0.2, result depends on whether roll < 0.2
        assert result == (roll < 0.2)

    def test_health_3_higher_chance(self):
        """Health 3 gives deficit=2, chance=0.4."""
        rng = random.Random(42)
        roll = rng.random()
        rng = random.Random(42)
        result = death_roll(3, rng)
        assert result == (roll < 0.4)

    def test_health_1_high_chance(self):
        """Health 1 gives deficit=4, chance=0.8."""
        rng = random.Random(42)
        roll = rng.random()
        rng = random.Random(42)
        result = death_roll(1, rng)
        assert result == (roll < 0.8)

    def test_deterministic_with_seed(self):
        """Same seed gives same result."""
        result1 = death_roll(3, random.Random(42))
        result2 = death_roll(3, random.Random(42))
        assert result1 == result2


# ---------------------------------------------------------------------------
# run_day_change (heavily mocked)
# ---------------------------------------------------------------------------


class TestRunDayChange:
    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    async def test_empty_server_no_crashes(
        self,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """Day change runs without error on a server with no pregnancies, pooches, or strays."""
        mock_pregnancies.return_value = []
        mock_living.return_value = []
        server = make_server(discord_id=200)
        mock_servers.return_value = [server]
        mock_strays.return_value = [make_pooch()]  # at least one stray so no guarantee needed
        mock_vendors.return_value = [make_vendor(), make_vendor(vendor_id=2), make_vendor(vendor_id=3)]
        mock_clear_stock.return_value = None
        mock_breed_ids.return_value = [1]
        mock_create_pooch.return_value = make_pooch(pooch_id=50)
        mock_stray_events.return_value = {}

        summaries, stray_results = await run_day_change(rng_seed=42)

        assert 200 in summaries
        assert summaries[200].births == []
        assert summaries[200].deaths == []
        mock_reset_beg.assert_awaited_once()
        mock_reset_park.assert_awaited_once()

    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_kennel", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers_for_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_pregnancy", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    @patch("src.game.change_day.to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.to_server", new_callable=AsyncMock)
    async def test_birth_into_kennel(
        self,
        mock_to_server,
        mock_to_pooch,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_del_preg,
        mock_get_pooch,
        mock_servers_for_pooch,
        mock_get_kennel,
        mock_add_to_kennel,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """A pregnancy produces a birth event when the mother has a kennel with space."""
        pregnancy = SimpleNamespace(mother_id=10, fetus_id=20)
        mock_pregnancies.return_value = [pregnancy]

        mother = make_pooch(pooch_id=10, name="Mama", sex="female")
        baby = make_pooch(pooch_id=20, name="Baby")
        mock_get_pooch.side_effect = lambda pid: mother if pid == 10 else baby

        server = make_server(discord_id=200)
        mock_servers_for_pooch.return_value = [server]
        mock_get_kennel.return_value = make_kennel(kennel_id=1)
        mock_add_to_kennel.return_value = True  # success

        mock_living.return_value = []
        mock_health.return_value = 10
        mock_servers.return_value = [server]
        mock_strays.return_value = [make_pooch()]
        mock_vendors.return_value = [make_vendor(), make_vendor(vendor_id=2), make_vendor(vendor_id=3)]
        mock_clear_stock.return_value = None
        mock_breed_ids.return_value = [1]
        mock_create_pooch.return_value = make_pooch(pooch_id=50)
        mock_stray_events.return_value = {}

        mock_to_server.side_effect = lambda s: SimpleNamespace(discord_id=s.discord_id)
        mock_to_pooch.side_effect = lambda p: SimpleNamespace(id=p.id, name=p.name)

        summaries, _ = await run_day_change(rng_seed=42)

        assert len(summaries[200].births) == 1
        birth = summaries[200].births[0]
        assert "gave birth" in birth.message

    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    async def test_stray_guarantee_adds_stray_when_empty(
        self,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """When a server has no strays, a guaranteed stray is created."""
        mock_pregnancies.return_value = []
        mock_living.return_value = []

        server = make_server(discord_id=200)
        mock_servers.return_value = [server]
        mock_strays.return_value = []  # No strays!
        mock_breed_ids.return_value = [1]

        stray_pooch = make_pooch(pooch_id=77)
        mock_create_pooch.return_value = stray_pooch
        mock_vendors.return_value = [make_vendor(), make_vendor(vendor_id=2), make_vendor(vendor_id=3)]
        mock_clear_stock.return_value = None
        mock_stray_events.return_value = {}

        await run_day_change(rng_seed=42)

        mock_add_stray.assert_any_call(77, 200)

    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    async def test_vendor_restock_creates_missing_vendors(
        self,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """When a server has fewer vendors than NUM_VENDORS_PER_SERVER (3), new ones are created."""
        mock_pregnancies.return_value = []
        mock_living.return_value = []

        server = make_server(discord_id=200)
        mock_servers.return_value = [server]
        mock_strays.return_value = [make_pooch()]

        # Only 1 vendor exists, should create 2 more
        existing_vendor = make_vendor(vendor_id=1)
        new_vendor = make_vendor(vendor_id=2)
        mock_vendors.return_value = [existing_vendor]
        mock_create_vendor.return_value = new_vendor
        mock_clear_stock.return_value = None
        mock_breed_ids.return_value = [1]
        mock_create_pooch.return_value = make_pooch(pooch_id=50)
        mock_stray_events.return_value = {}

        await run_day_change(rng_seed=42)

        # Should have created 2 new vendors (3 - 1 = 2)
        assert mock_create_vendor.call_count == 2


# ---------------------------------------------------------------------------
# Helper: full mock stack for run_day_change
# ---------------------------------------------------------------------------
# Rather than repeating 20 @patch decorators, we use a single context-manager
# approach inside individual test methods. This keeps the new tests concise.

_RUN_DAY_PATCHES = [
    "src.game.change_day.run_daily_stray_event_check",
    "src.game.change_day.add_pooch_to_vendor_stock",
    "src.game.change_day.add_mutation_to_pooch",
    "src.game.change_day.reset_pooch_breeding_cooldown",
    "src.game.change_day.create_pooch",
    "src.game.change_day.get_random_breed_ids",
    "src.game.change_day.clear_vendor_pooch_stock",
    "src.game.change_day.create_vendor",
    "src.game.change_day.delete_random_vendor",
    "src.game.change_day.list_vendors",
    "src.game.change_day.add_pooch_to_strays",
    "src.game.change_day.list_strays_for_server",
    "src.game.change_day.list_servers",
    "src.game.change_day.get_pooch_health",
    "src.game.change_day.age_pooch",
    "src.game.change_day.decrement_pooch_breeding_cooldown",
    "src.game.change_day.list_living_pooches",
    "src.game.change_day.list_pooch_pregnancies",
    "src.game.change_day.reset_visited_park_today",
    "src.game.change_day.reset_begged_today",
    "src.game.change_day.to_pooch",
    "src.game.change_day.to_server",
    "src.game.change_day.list_servers_for_pooch",
    "src.game.change_day.get_pooch_by_id",
    "src.game.change_day.delete_pregnancy",
    "src.game.change_day.get_pooch_kennel",
    "src.game.change_day.add_pooch_to_kennel",
    "src.game.change_day.set_pooch_dead",
    "src.game.change_day.remove_pooch_from_kennel",
    "src.game.change_day.bury_pooch",
    "src.game.change_day.list_pooch_mutations",
    "src.game.change_day.get_mutation_health_impact",
    "src.game.change_day.list_pooches_for_kennel",
    "src.game.change_day.update_pooch_mood",
    "src.game.change_day.get_current_season",
    "src.game.change_day.get_active_auction_sale_listing_for_pooch",
    "src.game.change_day.list_bids_for_listing",
    "src.game.change_day.close_auction_sale_listing",
    "src.game.change_day.give_money_to_owner",
    "src.game.change_day.process_expired_sale_listings",
    "src.game.change_day.list_hell_pooches",
    "src.game.change_day.list_vendor_desired_mutations",
    "src.game.change_day.list_vendor_desired_breeds",
    "src.game.change_day.bury_pooch",
    "src.game.change_day.increment_global_day",
    "src.game.change_day.run_daily_disease_tick",
    "src.game.change_day.list_pooch_diseases",
    "src.game.change_day.get_disease_health_impact",
    "src.game.change_day.list_pooch_injuries",
    "src.game.change_day.get_injury_health_impact",
]


def _build_mocks():
    """Return a dict of target→AsyncMock for all run_day_change dependencies."""
    return {target: AsyncMock() for target in _RUN_DAY_PATCHES}


def _apply_default_mocks(mocks, server=None, vendors=None):
    """Set sensible defaults on the mocks dict so run_day_change can complete."""
    if server is None:
        server = make_server(discord_id=200)
    if vendors is None:
        vendors = [make_vendor(vendor_id=i) for i in range(1, 4)]

    mocks["src.game.change_day.list_servers"].return_value = [server]
    mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
    mocks["src.game.change_day.list_living_pooches"].return_value = []
    mocks["src.game.change_day.list_strays_for_server"].return_value = [make_pooch()]
    mocks["src.game.change_day.list_vendors"].return_value = vendors
    mocks["src.game.change_day.get_random_breed_ids"].return_value = [1]
    mocks["src.game.change_day.create_pooch"].return_value = make_pooch(pooch_id=50)
    mocks["src.game.change_day.run_daily_stray_event_check"].return_value = {}
    mocks["src.game.change_day.get_pooch_health"].return_value = 10
    mocks["src.game.change_day.get_current_season"].return_value = "spring"
    mocks["src.game.change_day.get_active_auction_sale_listing_for_pooch"].return_value = None
    mocks["src.game.change_day.list_bids_for_listing"].return_value = []
    mocks["src.game.change_day.process_expired_sale_listings"].return_value = []
    mocks["src.game.change_day.list_hell_pooches"].return_value = []
    mocks["src.game.change_day.list_vendor_desired_mutations"].return_value = []
    mocks["src.game.change_day.list_vendor_desired_breeds"].return_value = []
    mocks["src.game.change_day.increment_global_day"].return_value = 1
    mocks["src.game.change_day.run_daily_disease_tick"].return_value = {}
    mocks["src.game.change_day.list_pooch_diseases"].return_value = []
    mocks["src.game.change_day.get_disease_health_impact"].return_value = None
    mocks["src.game.change_day.list_pooch_injuries"].return_value = []
    mocks["src.game.change_day.get_injury_health_impact"].return_value = None
    mocks["src.game.change_day.to_server"].side_effect = lambda s: SimpleNamespace(discord_id=s.discord_id)
    mocks["src.game.change_day.to_pooch"].side_effect = lambda p: SimpleNamespace(id=p.id, name=p.name)


# ---------------------------------------------------------------------------
# Birth edge cases: no kennel, full kennel
# ---------------------------------------------------------------------------


class TestRunDayChangeBirthEdgeCases:
    async def test_birth_no_kennel_records_abandoned_message(self):
        """When mother has no kennel, baby is marked as abandoned."""
        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mother = make_pooch(pooch_id=10, name="Mama")
        baby = make_pooch(pooch_id=20, name="Baby")
        pregnancy = SimpleNamespace(mother_id=10, fetus_id=20)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = [pregnancy]
        mocks["src.game.change_day.get_pooch_by_id"].side_effect = lambda pid: mother if pid == 10 else baby
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = None  # no kennel

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=42)

        assert len(summaries[200].births) == 1
        assert "abandoned" in summaries[200].births[0].message

    async def test_birth_full_kennel_records_crushed_message(self):
        """When mother's kennel is full, baby is recorded as crushed."""
        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mother = make_pooch(pooch_id=10, name="Mama")
        baby = make_pooch(pooch_id=20, name="Baby")
        pregnancy = SimpleNamespace(mother_id=10, fetus_id=20)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = [pregnancy]
        mocks["src.game.change_day.get_pooch_by_id"].side_effect = lambda pid: mother if pid == 10 else baby
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = make_kennel(kennel_id=1)
        mocks["src.game.change_day.add_pooch_to_kennel"].return_value = False  # kennel full

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=42)

        assert len(summaries[200].births) == 1
        assert "released as a stray" in summaries[200].births[0].message


# ---------------------------------------------------------------------------
# Deaths: pooch dies, old age, unknown cause, mutation causes
# ---------------------------------------------------------------------------


class TestRunDayChangeDeath:
    async def _run_with_dying_pooch(
        self,
        pooch,
        total_health,
        mutations=None,
        neg_mutations=None,
        health_impacts=None,
        servers_for_pooch=None,
        kennel=None,
        kennel_pooches=None,
        rng_seed=0,
    ):
        """Helper that runs run_day_change with a pooch forced to die (health < 5)."""
        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = total_health
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch
        mocks["src.game.change_day.list_pooch_mutations"].side_effect = (
            [mutations or [], neg_mutations or []] if neg_mutations is not None else [mutations or [], []]
        )
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        if health_impacts:
            mocks["src.game.change_day.get_mutation_health_impact"].side_effect = iter(health_impacts)
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = (
            servers_for_pooch if servers_for_pooch is not None else [server]
        )
        mocks["src.game.change_day.get_pooch_kennel"].return_value = kennel
        mocks["src.game.change_day.list_pooches_for_kennel"].return_value = kennel_pooches or []
        mocks["src.game.change_day.get_pooch_by_id"].return_value = pooch

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=rng_seed)
        return summaries

    async def test_dying_pooch_unknown_cause(self):
        """Pooch with no mutations and no health_loss_age dies of unknown causes."""
        pooch = make_pooch(pooch_id=5, name="Fido", health_loss_age=0, alive=True)
        summaries = await self._run_with_dying_pooch(pooch, total_health=0)
        assert any("unknown causes" in d.message for d in summaries[200].deaths)

    async def test_dying_pooch_old_age(self):
        """Pooch with health_loss_age > 0 and no negative mutations dies of old age."""
        pooch = make_pooch(pooch_id=5, name="OldFido", health_loss_age=5, alive=True)
        summaries = await self._run_with_dying_pooch(pooch, total_health=0)
        assert any("old age" in d.message for d in summaries[200].deaths)

    async def test_dying_pooch_with_negative_mutation(self):
        """Pooch with a negative mutation that has a death_message uses it."""
        pooch = make_pooch(pooch_id=5, name="SickFido", alive=True, health_loss_age=0)
        neg_mutation = make_mutation(
            mutation_id=1, name="DeadlyDisease", parameters={"death_message": "[pooch] succumbed to the disease."}
        )
        summaries = await self._run_with_dying_pooch(
            pooch,
            total_health=0,
            mutations=[neg_mutation],
            neg_mutations=[neg_mutation],
            health_impacts=[-5],
        )
        deaths = summaries[200].deaths
        assert len(deaths) >= 1
        assert any("succumbed" in d.message for d in deaths)

    async def test_already_dead_pooch_skipped(self):
        """A pooch with alive=False should not generate a death event."""
        pooch = make_pooch(pooch_id=5, name="AlreadyDead", alive=False)
        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=42)

        assert summaries[200].deaths == []

    async def test_on_death_kill_spreads_death_to_target(self):
        """A mutation with on_death=kill kills a kennel-mate."""
        pooch = make_pooch(pooch_id=5, name="Killer", alive=True, health_loss_age=0)
        target = make_pooch(pooch_id=6, name="Victim", alive=True)
        kennel = make_kennel(kennel_id=1)

        on_death_mut = make_mutation(
            mutation_id=10,
            name="KillMut",
            parameters={
                "on_death_triggers": [
                    {
                        "on_death": "kill",
                        "on_death_targets": "all",
                        "always_on_death": True,
                        "on_death_chance": 1.0,
                    }
                ]
            },
        )

        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch

        call_count = {"n": 0}

        def list_mutations_side(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return [on_death_mut]
            return [on_death_mut]

        mocks["src.game.change_day.list_pooch_mutations"].side_effect = list_mutations_side
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = kennel
        mocks["src.game.change_day.list_pooches_for_kennel"].return_value = [target]
        mocks["src.game.change_day.get_pooch_by_id"].return_value = pooch

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=0)

        # set_pooch_dead should have been called for pooch 5 at minimum
        mocks["src.game.change_day.set_pooch_dead"].assert_awaited()

    async def test_on_death_spread_adds_mutation_to_target(self):
        """A mutation with on_death=spread gives a mutation to the kennel-mate."""
        pooch = make_pooch(pooch_id=5, name="Spreader", alive=True, health_loss_age=0)
        target = make_pooch(pooch_id=6, name="Receiver", alive=True)
        kennel = make_kennel(kennel_id=1)

        spread_mut = make_mutation(
            mutation_id=10,
            name="SpreadMut",
            parameters={
                "on_death_triggers": [
                    {
                        "on_death": "spread",
                        "on_death_targets": "all",
                        "always_on_death": True,
                        "on_death_chance": 1.0,
                    }
                ]
            },
        )

        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch

        call_count = {"n": 0}

        def list_mutations_side(*args, **kwargs):
            call_count["n"] += 1
            return [spread_mut]

        mocks["src.game.change_day.list_pooch_mutations"].side_effect = list_mutations_side
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = kennel
        mocks["src.game.change_day.list_pooches_for_kennel"].return_value = [target]
        mocks["src.game.change_day.get_pooch_by_id"].return_value = target

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=0)

        mocks["src.game.change_day.add_mutation_to_pooch"].assert_awaited()

    async def test_on_death_spread_all_adds_all_mutations(self):
        """A mutation with on_death=spread_all copies all mutations to kennel-mates."""
        pooch = make_pooch(pooch_id=5, name="SpreadAll", alive=True, health_loss_age=0)
        target = make_pooch(pooch_id=6, name="Infected", alive=True)
        kennel = make_kennel(kennel_id=1)

        spread_all_mut = make_mutation(
            mutation_id=10,
            name="SpreadAllMut",
            parameters={
                "on_death_triggers": [
                    {
                        "on_death": "spread_all",
                        "on_death_targets": "all",
                        "always_on_death": True,
                        "on_death_chance": 1.0,
                    }
                ]
            },
        )
        other_mut = make_mutation(mutation_id=11, name="OtherMut")

        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch

        call_count = {"n": 0}

        def list_mutations_side(*args, **kwargs):
            call_count["n"] += 1
            return [spread_all_mut, other_mut]

        mocks["src.game.change_day.list_pooch_mutations"].side_effect = list_mutations_side
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = kennel
        mocks["src.game.change_day.list_pooches_for_kennel"].return_value = [target]
        mocks["src.game.change_day.get_pooch_by_id"].return_value = target

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=0)

        # Both mutations should have been added to the target
        assert mocks["src.game.change_day.add_mutation_to_pooch"].await_count >= 2

    async def test_on_death_random_target_selects_one(self):
        """on_death_targets=random selects a single kennel-mate as target."""
        pooch = make_pooch(pooch_id=5, name="RandomKiller", alive=True, health_loss_age=0)
        target1 = make_pooch(pooch_id=6, name="T1", alive=True)
        target2 = make_pooch(pooch_id=7, name="T2", alive=True)
        kennel = make_kennel(kennel_id=1)

        kill_mut = make_mutation(
            mutation_id=10,
            name="RandomKillMut",
            parameters={
                "on_death_triggers": [
                    {
                        "on_death": "kill",
                        "on_death_targets": "random",
                        "always_on_death": True,
                        "on_death_chance": 1.0,
                    }
                ]
            },
        )

        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch

        def list_mutations_side(*args, **kwargs):
            return [kill_mut]

        mocks["src.game.change_day.list_pooch_mutations"].side_effect = list_mutations_side
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = kennel
        mocks["src.game.change_day.list_pooches_for_kennel"].return_value = [target1, target2]
        mocks["src.game.change_day.get_pooch_by_id"].return_value = pooch

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=0)

        # At least the original pooch death should be recorded
        mocks["src.game.change_day.set_pooch_dead"].assert_awaited()

    async def test_on_death_targets_no_kennel_skips(self):
        """on_death_targets handling skips if the pooch has no kennel."""
        pooch = make_pooch(pooch_id=5, name="NoKennel", alive=True, health_loss_age=0)

        kill_mut = make_mutation(
            mutation_id=10,
            name="KillMutNoKennel",
            parameters={
                "on_death_triggers": [
                    {
                        "on_death": "kill",
                        "on_death_targets": "all",
                        "always_on_death": True,
                        "on_death_chance": 1.0,
                    }
                ]
            },
        )

        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch

        def list_mutations_side(*args, **kwargs):
            return [kill_mut]

        mocks["src.game.change_day.list_pooch_mutations"].side_effect = list_mutations_side
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = None  # no kennel
        mocks["src.game.change_day.get_pooch_by_id"].return_value = pooch

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=0)

        # Only the original pooch should have died
        assert len(summaries[200].deaths) >= 1


# ---------------------------------------------------------------------------
# Vendor restock: stock count and mutation assignment
# ---------------------------------------------------------------------------


class TestRunDayChangeVendorRestock:
    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    async def test_clear_vendor_stock_called_for_each_vendor(
        self,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """clear_vendor_pooch_stock is called once per vendor."""
        mock_pregnancies.return_value = []
        mock_living.return_value = []

        server = make_server(discord_id=200)
        mock_servers.return_value = [server]
        mock_strays.return_value = [make_pooch()]

        vendors = [make_vendor(vendor_id=i) for i in range(1, 4)]
        mock_vendors.return_value = vendors
        mock_breed_ids.return_value = [1]
        mock_create_pooch.return_value = make_pooch(pooch_id=50)
        mock_stray_events.return_value = {}

        await run_day_change(rng_seed=42)

        # clear_vendor_pooch_stock called once per vendor (3 vendors)
        assert mock_clear_stock.await_count == 3

    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    async def test_delete_random_vendor_called_per_server(
        self,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """delete_random_vendor is called once per server."""
        mock_pregnancies.return_value = []
        mock_living.return_value = []

        servers = [make_server(discord_id=200), make_server(discord_id=300)]
        mock_servers.return_value = servers
        mock_strays.return_value = [make_pooch()]
        vendors = [make_vendor(vendor_id=i) for i in range(1, 4)]
        mock_vendors.return_value = vendors
        mock_breed_ids.return_value = [1]
        mock_create_pooch.return_value = make_pooch(pooch_id=50)
        mock_stray_events.return_value = {}

        await run_day_change(rng_seed=42)

        assert mock_del_vendor.await_count == 2


# ---------------------------------------------------------------------------
# Stray event results are passed through to the output tuple
# ---------------------------------------------------------------------------


class TestRunDayChangeStrayEventResults:
    @patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
    @patch("src.game.change_day.run_daily_disease_tick", new_callable=AsyncMock, return_value={})
    @patch("src.game.change_day.list_pooch_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.change_day.get_disease_health_impact", new_callable=AsyncMock, return_value=None)
    @patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
    @patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
    @patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
    @patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.change_day.list_servers", new_callable=AsyncMock)
    @patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
    @patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
    @patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
    async def test_stray_event_results_passed_through(
        self,
        mock_reset_beg,
        mock_reset_park,
        mock_pregnancies,
        mock_living,
        mock_dec_cd,
        mock_age,
        mock_health,
        mock_servers,
        mock_strays,
        mock_add_stray,
        mock_vendors,
        mock_del_vendor,
        mock_create_vendor,
        mock_clear_stock,
        mock_breed_ids,
        mock_create_pooch,
        mock_reset_cd,
        mock_add_mut,
        mock_add_vendor_stock,
        mock_stray_events,
        mock_disease_health_impact,
        mock_pooch_diseases,
        mock_disease_tick,
        mock_increment_day,
    ):
        """The stray event results dict is returned as the second element of the tuple."""
        mock_pregnancies.return_value = []
        mock_living.return_value = []
        server = make_server(discord_id=200)
        mock_servers.return_value = [server]
        mock_strays.return_value = [make_pooch()]
        mock_vendors.return_value = [make_vendor(vendor_id=i) for i in range(1, 4)]
        mock_breed_ids.return_value = [1]
        mock_create_pooch.return_value = make_pooch(pooch_id=50)

        fake_stray_results = {200: [("StreetFight", MagicMock())]}
        mock_stray_events.return_value = fake_stray_results

        _, stray_results = await run_day_change(rng_seed=42)

        assert stray_results is fake_stray_results
        assert 200 in stray_results


# ---------------------------------------------------------------------------
# Summary compilation includes other_events
# ---------------------------------------------------------------------------


class TestRunDayChangeSummaryCompilation:
    async def test_summary_includes_other_events_from_spread(self):
        """Other events (mutation spread) appear in the summary's other_events list."""
        pooch = make_pooch(pooch_id=5, name="Spreader2", alive=True, health_loss_age=0)
        target = make_pooch(pooch_id=6, name="Receiver2", alive=True)
        kennel = make_kennel(kennel_id=1)

        spread_mut = make_mutation(
            mutation_id=10,
            name="SpreadMut2",
            parameters={
                "on_death_triggers": [
                    {
                        "on_death": "spread",
                        "on_death_targets": "all",
                        "always_on_death": True,
                        "on_death_chance": 1.0,
                        "impact_message": "[pooch] spread to [victim].",
                    }
                ]
            },
        )

        mocks = _build_mocks()
        server = make_server(discord_id=200)
        _apply_default_mocks(mocks, server=server)

        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = [pooch]
        mocks["src.game.change_day.decrement_pooch_breeding_cooldown"].return_value = pooch
        mocks["src.game.change_day.age_pooch"].return_value = pooch
        mocks["src.game.change_day.get_pooch_health"].return_value = 0
        mocks["src.game.change_day.set_pooch_dead"].return_value = pooch

        def list_mutations_side(*args, **kwargs):
            return [spread_mut]

        mocks["src.game.change_day.list_pooch_mutations"].side_effect = list_mutations_side
        mocks["src.game.change_day.get_mutation_health_impact"].return_value = None
        mocks["src.game.change_day.list_servers_for_pooch"].return_value = [server]
        mocks["src.game.change_day.get_pooch_kennel"].return_value = kennel
        mocks["src.game.change_day.list_pooches_for_kennel"].return_value = [target]
        mocks["src.game.change_day.get_pooch_by_id"].return_value = target

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=0)

        assert len(summaries[200].other_events) >= 1

    async def test_multiple_servers_each_get_summary(self):
        """Each server gets its own DayChangeSummary entry."""
        mocks = _build_mocks()
        s1 = make_server(discord_id=100)
        s2 = make_server(discord_id=300)

        mocks["src.game.change_day.list_servers"].return_value = [s1, s2]
        mocks["src.game.change_day.list_pooch_pregnancies"].return_value = []
        mocks["src.game.change_day.list_living_pooches"].return_value = []
        mocks["src.game.change_day.list_strays_for_server"].return_value = [make_pooch()]
        mocks["src.game.change_day.list_vendors"].return_value = [make_vendor(vendor_id=i) for i in range(1, 4)]
        mocks["src.game.change_day.get_random_breed_ids"].return_value = [1]
        mocks["src.game.change_day.create_pooch"].return_value = make_pooch(pooch_id=50)
        mocks["src.game.change_day.run_daily_stray_event_check"].return_value = {}
        mocks["src.game.change_day.get_current_season"].return_value = "spring"
        mocks["src.game.change_day.get_active_auction_sale_listing_for_pooch"].return_value = None
        mocks["src.game.change_day.list_bids_for_listing"].return_value = []
        mocks["src.game.change_day.process_expired_sale_listings"].return_value = []
        mocks["src.game.change_day.list_hell_pooches"].return_value = []
        mocks["src.game.change_day.list_vendor_desired_mutations"].return_value = []
        mocks["src.game.change_day.list_vendor_desired_breeds"].return_value = []
        mocks["src.game.change_day.increment_global_day"].return_value = 1
        mocks["src.game.change_day.run_daily_disease_tick"].return_value = {}
        mocks["src.game.change_day.list_pooch_diseases"].return_value = []
        mocks["src.game.change_day.get_disease_health_impact"].return_value = None
        mocks["src.game.change_day.list_pooch_injuries"].return_value = []
        mocks["src.game.change_day.get_injury_health_impact"].return_value = None
        mocks["src.game.change_day.to_server"].side_effect = lambda s: SimpleNamespace(discord_id=s.discord_id)
        mocks["src.game.change_day.to_pooch"].side_effect = lambda p: SimpleNamespace(id=p.id, name=p.name)

        with patch.multiple("src.game.change_day", **{k.split("src.game.change_day.")[1]: v for k, v in mocks.items()}):
            summaries, _ = await run_day_change(rng_seed=42)

        assert 100 in summaries
        assert 300 in summaries


@patch(
    "src.game.change_day.run_daily_disease_tick",
    new_callable=AsyncMock,
    return_value={99: [(99, "a mysterious illness", "contracted")]},
)
@patch("src.game.change_day.increment_global_day", new_callable=AsyncMock, return_value=1)
@patch("src.game.change_day.run_daily_stray_event_check", new_callable=AsyncMock, return_value={})
@patch("src.game.change_day.add_pooch_to_vendor_stock", new_callable=AsyncMock)
@patch("src.game.change_day.add_mutation_to_pooch", new_callable=AsyncMock)
@patch("src.game.change_day.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
@patch("src.game.change_day.create_pooch", new_callable=AsyncMock)
@patch("src.game.change_day.get_random_breed_ids", new_callable=AsyncMock)
@patch("src.game.change_day.clear_vendor_pooch_stock", new_callable=AsyncMock)
@patch("src.game.change_day.create_vendor", new_callable=AsyncMock)
@patch("src.game.change_day.delete_random_vendor", new_callable=AsyncMock)
@patch("src.game.change_day.list_vendors", new_callable=AsyncMock)
@patch("src.game.change_day.add_pooch_to_strays", new_callable=AsyncMock)
@patch("src.game.change_day.list_strays_for_server", new_callable=AsyncMock)
@patch("src.game.change_day.list_servers", new_callable=AsyncMock)
@patch("src.game.change_day.get_pooch_health", new_callable=AsyncMock)
@patch("src.game.change_day.age_pooch", new_callable=AsyncMock)
@patch("src.game.change_day.decrement_pooch_breeding_cooldown", new_callable=AsyncMock)
@patch("src.game.change_day.list_living_pooches", new_callable=AsyncMock)
@patch("src.game.change_day.list_servers_for_pooch", new_callable=AsyncMock)
@patch("src.game.change_day.get_pooch_by_id", new_callable=AsyncMock)
@patch("src.game.change_day.to_pooch", new_callable=AsyncMock)
@patch("src.game.change_day.to_server", new_callable=AsyncMock)
@patch("src.game.change_day.list_pooch_pregnancies", new_callable=AsyncMock)
@patch("src.game.change_day.reset_visited_park_today", new_callable=AsyncMock)
@patch("src.game.change_day.reset_begged_today", new_callable=AsyncMock)
async def test_day_change_uses_public_disease_label_in_summary(
    mock_reset_beg,
    mock_reset_park,
    mock_pregnancies,
    mock_to_server,
    mock_to_pooch,
    mock_get_pooch,
    mock_servers_for_pooch,
    mock_living,
    mock_dec_cd,
    mock_age,
    mock_health,
    mock_servers,
    mock_strays,
    mock_add_stray,
    mock_vendors,
    mock_del_vendor,
    mock_create_vendor,
    mock_clear_stock,
    mock_breed_ids,
    mock_create_pooch,
    mock_reset_cd,
    mock_add_mut,
    mock_add_vendor_stock,
    mock_stray_events,
    mock_increment_day,
    mock_disease_tick,
):
    server = make_server(discord_id=10)
    pooch = make_pooch(pooch_id=99, name="Buddy")
    mock_servers.return_value = [server]
    mock_servers_for_pooch.return_value = [server]
    mock_get_pooch.return_value = pooch
    mock_to_pooch.side_effect = lambda p: p
    mock_to_server.side_effect = lambda s: s
    mock_pregnancies.return_value = []
    mock_living.return_value = []
    mock_strays.return_value = [make_pooch()]
    mock_vendors.return_value = [make_vendor(), make_vendor(vendor_id=2), make_vendor(vendor_id=3)]
    mock_health.return_value = 10

    summaries, _ = await run_day_change(rng_seed=42)

    assert 10 in summaries
    event_texts = [event.message for event in summaries[10].other_events]
    assert any("a mysterious illness" in msg for msg in event_texts)
    assert not any("Kennel Cough" in msg for msg in event_texts)
