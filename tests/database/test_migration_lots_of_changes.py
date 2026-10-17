"""Tests for the lots-of-changes upgrade (src/database/migrations/lots_of_changes.py) and its helpers."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.database.migrations import lots_of_changes as migration
from src.database.set import pooch_upkeep

MOD = "src.database.migrations.lots_of_changes"


def _scope(session):
    class _FakeScope:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    return _FakeScope()


def _result(scalars=None, rows=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars or []
    result.all.return_value = rows or []
    return result


class TestPoochUpkeep:
    def test_matches_size(self):
        # consumption: 1 + 0.1 * 10 = 2 ; mess: 2 + 0.15 * 10 = 3.5 -> 4
        assert pooch_upkeep(10, []) == (2, 4)

    def test_breed_modifiers_and_minimum(self):
        # mess: 2 + 1 + 1.5 = 4.5 -> 4 (Python rounds halves to even)
        assert pooch_upkeep(10, [{"consumption_mult": 2.0, "mess_output_add": 1}, None]) == (4, 4)
        assert pooch_upkeep(0, [{"consumption_mult": 0.0, "mess_output_mult": 0.0}]) == (1, 1)


class TestBackfillPregnancyTimers:
    async def test_only_mothers_without_a_timer_get_one(self):
        mother = SimpleNamespace(id=5, pregnancy_timer=None)
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[_result(scalars=[5, 5]), _result(scalars=[mother])])
        with patch(f"{MOD}.session_scope", return_value=_scope(session)):
            count = await migration._backfill_pregnancy_timers((15, 20), random.Random(0))
        assert count == 1
        assert 15 <= mother.pregnancy_timer <= 20

    async def test_no_pregnancies(self):
        session = MagicMock()
        session.execute = AsyncMock(return_value=_result(scalars=[]))
        with patch(f"{MOD}.session_scope", return_value=_scope(session)):
            assert await migration._backfill_pregnancy_timers((15, 20), random.Random(0)) == 0


class TestBackfillUpkeep:
    async def test_recomputes_from_size_and_breeds(self):
        big = SimpleNamespace(id=1, size=20, consumption=1, mess_output=2)
        mutt = SimpleNamespace(id=2, size=10, consumption=1, mess_output=2)
        session = MagicMock()
        session.execute = AsyncMock(
            side_effect=[_result(rows=[(1, {"consumption_mult": 2.0})]), _result(scalars=[big, mutt])]
        )
        with patch(f"{MOD}.session_scope", return_value=_scope(session)):
            assert await migration._backfill_upkeep() == 2
        assert (big.consumption, big.mess_output) == pooch_upkeep(20, [{"consumption_mult": 2.0}])
        assert (mutt.consumption, mutt.mess_output) == pooch_upkeep(10, [])


class TestStockKennels:
    async def test_tops_up_only_kennels_below_the_amount(self):
        empty = SimpleNamespace(id=1, food_stock=0)
        low = SimpleNamespace(id=2, food_stock=10)
        session = MagicMock()
        session.execute = AsyncMock(return_value=_result(scalars=[empty, low]))
        with patch(f"{MOD}.session_scope", return_value=_scope(session)):
            assert await migration._stock_kennels(48) == 2
        assert (empty.food_stock, low.food_stock) == (48, 48)
        # the query itself only selects kennels below the amount, so fuller kennels are never touched
        assert "food_stock <" in str(session.execute.await_args.args[0])


class TestSyncOwnerEventTimeouts:
    async def test_only_changes_events_whose_window_differs(self):
        fish = SimpleNamespace(name="Fish or Cheese", response_timeout=5)
        family = SimpleNamespace(name="Interested Family", response_timeout=7200)
        session = MagicMock()
        session.execute = AsyncMock(return_value=_result(scalars=[fish, family]))
        resources = {"other": {"Fish or Cheese": {"response_timeout": 7200}}, "fortune": {"Interested Family": {}}}
        with (
            patch(f"{MOD}.load_categorized_resource_objects", return_value=resources),
            patch(f"{MOD}.session_scope", return_value=_scope(session)),
        ):
            assert await migration._sync_owner_event_timeouts() == ["Fish or Cheese", "Interested Family"]
        # a file without response_timeout gets the loader's default, as on a reset
        assert (fish.response_timeout, family.response_timeout) == (7200, 3600)


class TestUpgradeOrder:
    async def test_runs_every_step_and_only_adds_catalog_rows(self):
        connection = MagicMock()
        connection.run_sync = AsyncMock(return_value=["table items"])
        engine = MagicMock()
        engine.begin.return_value = _scope(connection)
        loaders = {name: AsyncMock() for name in ("load_diseases", "load_injuries", "load_mutations", "load_items")}
        with (
            patch(f"{MOD}._get_engine", return_value=engine),
            patch.multiple(MOD, **loaders),
            patch(f"{MOD}._backfill_pregnancy_timers", new=AsyncMock(return_value=0)) as pregnancies,
            patch(f"{MOD}._backfill_upkeep", new=AsyncMock(return_value=0)) as upkeep,
            patch(f"{MOD}._sync_owner_event_timeouts", new=AsyncMock(return_value=[])) as retime,
            patch(f"{MOD}.validate_cross_references", new=AsyncMock()) as validate,
        ):
            await migration.upgrade(pregnancy_timer_range=(15, 20))
            with patch(f"{MOD}._stock_kennels", new=AsyncMock(return_value=0)) as stock:
                await migration.upgrade(pregnancy_timer_range=(15, 20))
                stock.assert_not_awaited()
                await migration.upgrade(pregnancy_timer_range=(15, 20), starting_food=48)
                stock.assert_awaited_once_with(48)
        connection.run_sync.assert_awaited_with(migration._sync_schema)
        for loader in loaders.values():
            loader.assert_awaited_with(only_missing=True)
        assert pregnancies.await_args.args[0] == (15, 20)
        upkeep.assert_awaited()
        retime.assert_awaited()
        validate.assert_awaited()


class TestLoadersOnlyMissing:
    async def test_existing_rows_are_kept_and_only_new_ones_added(self):
        from src.database.load.load_resources import items as items_loader

        session = MagicMock()
        session.execute = AsyncMock(return_value=_result(scalars=["Soap"]))
        catalog = {
            "Cleaning": {"Soap": {"parameters": {"price": 5, "mess_reduction": 5}}},
            "Food": {"Kibble": {"parameters": {"price": 5, "food_units": 10}}},
        }
        with (
            patch.object(items_loader, "_ITEMS_ROOT", MagicMock(exists=lambda: True)),
            patch.object(items_loader, "load_categorized_resource_objects", return_value=catalog),
            patch.object(items_loader, "session_scope", return_value=_scope(session)),
        ):
            await items_loader.load_items(only_missing=True)
        added = [call.args[0].name for call in session.add.call_args_list]
        assert added == ["Kibble"]
        # no DELETE was issued: the only query was the name lookup
        assert session.execute.await_count == 1
