"""Tests for src/game/change_day.py — death rolls and the daily tick."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.game import run_day_change
from tests.conftest import (
    make_pooch,
    make_server,
    make_vendor,
)

# ---------------------------------------------------------------------------
# Shared patch helpers for run_day_change
# ---------------------------------------------------------------------------

_PATCH_TARGETS = [
    "src.game.change_day.get_current_season",
    "src.game.change_day.increment_global_day",
    "src.game.change_day.list_servers",
    "src.game.change_day.list_strays_for_server",
    "src.game.change_day.add_pooch_to_strays",
    "src.game.change_day.get_random_breed_ids",
    "src.game.change_day.create_pooch",
    "src.game.change_day.list_vendors",
    "src.game.change_day.delete_random_vendor",
    "src.game.change_day.create_vendor",
    "src.game.change_day.list_vendor_desired_breeds",
    "src.game.change_day.list_vendor_desired_mutations",
    "src.game.change_day.clear_vendor_pooch_stock",
    "src.game.change_day.reset_pooch_breeding_cooldown",
    "src.game.change_day.add_mutation_to_pooch",
    "src.game.change_day.add_pooch_to_vendor_stock",
    "src.game.change_day.process_expired_sale_listings",
    "src.game.change_day.run_daily_stray_event_check",
    # daily owner flag resets
    "src.game.change_day.reset_begged_today",
    "src.game.change_day.reset_visited_park_today",
    "src.game.change_day.list_owners",
    "src.game.change_day.set_owner_hand_cleaned_today",
]


def _apply_defaults(mocks: dict, *, server=None, vendors=None):
    """Set sensible defaults so run_day_change can complete without hitting the DB."""
    server = server or make_server(discord_id=200)
    vendors = vendors or [make_vendor(vendor_id=i) for i in range(1, 4)]

    mocks["src.game.change_day.get_current_season"].return_value = "spring"
    mocks["src.game.change_day.increment_global_day"].return_value = 1
    mocks["src.game.change_day.list_servers"].return_value = [server]
    mocks["src.game.change_day.list_strays_for_server"].return_value = [make_pooch()]
    mocks["src.game.change_day.add_pooch_to_strays"].return_value = None
    mocks["src.game.change_day.get_random_breed_ids"].return_value = [1]
    mocks["src.game.change_day.create_pooch"].return_value = make_pooch(pooch_id=50)
    mocks["src.game.change_day.list_vendors"].return_value = vendors
    mocks["src.game.change_day.delete_random_vendor"].return_value = None
    mocks["src.game.change_day.create_vendor"].return_value = make_vendor(vendor_id=99)
    mocks["src.game.change_day.list_vendor_desired_breeds"].return_value = []
    mocks["src.game.change_day.list_vendor_desired_mutations"].return_value = []
    mocks["src.game.change_day.clear_vendor_pooch_stock"].return_value = None
    mocks["src.game.change_day.reset_pooch_breeding_cooldown"].return_value = None
    mocks["src.game.change_day.add_mutation_to_pooch"].return_value = None
    mocks["src.game.change_day.add_pooch_to_vendor_stock"].return_value = None
    mocks["src.game.change_day.process_expired_sale_listings"].return_value = []
    mocks["src.game.change_day.run_daily_stray_event_check"].return_value = {}
    mocks["src.game.change_day.reset_begged_today"].return_value = None
    mocks["src.game.change_day.reset_visited_park_today"].return_value = None
    mocks["src.game.change_day.list_owners"].return_value = []
    mocks["src.game.change_day.set_owner_hand_cleaned_today"].return_value = None


# ---------------------------------------------------------------------------
# run_day_change — now returns stray_results dict only
# ---------------------------------------------------------------------------


class TestRunDayChange:
    async def test_returns_stray_results_dict(self):
        """run_day_change returns the stray event results dict directly."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)
        fake_results = {200: [("StreetFight", MagicMock())]}
        mocks["src.game.change_day.run_daily_stray_event_check"].return_value = fake_results

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            result = await run_day_change(rng_seed=42)

        assert result is fake_results

    async def test_no_crashes_empty_server(self):
        """run_day_change completes without error on a server with no strays or vendors."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            result = await run_day_change(rng_seed=42)

        assert isinstance(result, dict)

    async def test_increment_global_day_called(self):
        """increment_global_day is called exactly once per run."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            await run_day_change(rng_seed=42)

        mocks["src.game.change_day.increment_global_day"].assert_awaited_once()

    async def test_process_expired_sale_listings_called(self):
        """process_expired_sale_listings is called once for auction expiry."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            await run_day_change(rng_seed=42)

        mocks["src.game.change_day.process_expired_sale_listings"].assert_awaited_once()


# ---------------------------------------------------------------------------
# Minimum stray guarantee
# ---------------------------------------------------------------------------


class TestRunDayChangeStrayGuarantee:
    async def test_stray_guarantee_adds_stray_when_empty(self):
        """When a server has no strays, a new stray is created and added."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)
        mocks["src.game.change_day.list_strays_for_server"].return_value = []
        new_stray = make_pooch(pooch_id=99)
        mocks["src.game.change_day.create_pooch"].return_value = new_stray

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            await run_day_change(rng_seed=42)

        mocks["src.game.change_day.add_pooch_to_strays"].assert_awaited_once_with(new_stray.id, 200)

    async def test_stray_guarantee_skipped_when_strays_exist(self):
        """When a server already has strays, add_pooch_to_strays is not called."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)
        mocks["src.game.change_day.list_strays_for_server"].return_value = [make_pooch()]

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            await run_day_change(rng_seed=42)

        mocks["src.game.change_day.add_pooch_to_strays"].assert_not_awaited()


# ---------------------------------------------------------------------------
# Vendor restock
# ---------------------------------------------------------------------------


class TestRunDayChangeVendorRestock:
    async def test_clear_vendor_stock_called_for_each_vendor(self):
        """clear_vendor_pooch_stock is called once per vendor."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        vendors = [make_vendor(vendor_id=i) for i in range(1, 4)]
        _apply_defaults(mocks, vendors=vendors)

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            await run_day_change(rng_seed=42)

        assert mocks["src.game.change_day.clear_vendor_pooch_stock"].await_count == 3

    async def test_delete_random_vendor_called_per_server(self):
        """delete_random_vendor is called once per server."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)
        servers = [make_server(discord_id=200), make_server(discord_id=300)]
        mocks["src.game.change_day.list_servers"].return_value = servers

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            await run_day_change(rng_seed=42)

        assert mocks["src.game.change_day.delete_random_vendor"].await_count == 2


# ---------------------------------------------------------------------------
# Stray event results
# ---------------------------------------------------------------------------


class TestRunDayChangeStrayEventResults:
    async def test_stray_event_results_returned_directly(self):
        """The stray event results dict is returned as the sole return value."""
        mocks = {t: AsyncMock() for t in _PATCH_TARGETS}
        _apply_defaults(mocks)
        fake_stray_results = {200: [("StreetFight", MagicMock())]}
        mocks["src.game.change_day.run_daily_stray_event_check"].return_value = fake_stray_results

        with patch.multiple("src.game.change_day", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            stray_results = await run_day_change(rng_seed=42)

        assert stray_results is fake_stray_results
        assert 200 in stray_results
