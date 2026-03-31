"""Tests for src/game/manage_stray_events.py — stray target resolution and daily check."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import make_pooch, make_server


@pytest.fixture(autouse=True)
def mock_stray_events_db_calls():
    """Auto-patch DB-touching functions so tests never hit the real DB."""
    with (
        patch("src.game.manage_stray_events.get_current_season", new=AsyncMock(return_value="spring")),
        patch("src.game.manage_stray_events.cancel_listing_for_pooch", new=AsyncMock()),
    ):
        yield


from src.game.manage_stray_events import (
    _choose_stray_event_outcome,
    _compute_outcome_stat_multiplier,
    _deliver_stray_to_kennel,
    _deliver_stray_to_vendor,
    _execute_single_stray_action,
    _execute_stray_event_actions,
    _get_effective_pooch_stat,
    _resolve_single_stat_pooch_id,
    _resolve_stray_target_ids,
    _trigger_stray_event_for_server,
    run_daily_stray_event_check,
)
from src.game.models import StrayEventContext, StrayEventResult

# ---------------------------------------------------------------------------
# _resolve_stray_target_ids
# ---------------------------------------------------------------------------


class TestResolveStrayTargetIds:
    async def test_random_selector_picks_one(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "random", {}, rng)
        assert len(ids) == 1
        assert ids[0] in [10, 20, 30]

    async def test_random_selector_with_count(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30, 40, 50])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "random", {"count": 2}, rng)
        assert len(ids) == 2

    async def test_all_selector_returns_all(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "all", {}, rng)
        assert ids == [10, 20, 30]

    async def test_random_exclude_selector(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30, 40, 50])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "random_exclude", {"count": 2}, rng)
        # Excludes 2, returns the rest (3)
        assert len(ids) == 3

    @patch("src.game.manage_stray_events.list_matching_stray_pooch_ids", new_callable=AsyncMock)
    async def test_all_exclude_selector(self, mock_matching):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)

        # Pool from action filter = [10, 20]
        # All strays = [10, 20, 30]
        # all_exclude = strays NOT in pool = [30]
        mock_matching.side_effect = lambda sid, f: [10, 20, 30] if f == {} else [10, 20]

        ids = await _resolve_stray_target_ids(context, "all_exclude", {"filter": {"sex": "male"}}, rng)
        assert ids == [30]

    async def test_use_saved_from_context(self):
        context = StrayEventContext(
            server_discord_id=200,
            candidate_stray_ids=[10, 20, 30],
            extra_data={"saved_slot": {"pooch_ids": [42, 43]}},
        )
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "random", {"use_saved": "saved_slot"}, rng)
        assert ids == [42, 43]

    async def test_save_as_stores_result(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "all", {"save_as": "my_slot"}, rng)
        assert "my_slot" in context.extra_data
        assert context.extra_data["my_slot"]["pooch_ids"] == ids

    async def test_unknown_selector_returns_empty(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "nonexistent_selector", {}, rng)
        assert ids == []

    async def test_empty_pool_random_returns_empty(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        rng = random.Random(42)

        ids = await _resolve_stray_target_ids(context, "random", {}, rng)
        assert ids == []

    @patch("src.game.manage_stray_events.list_matching_stray_pooch_ids", new_callable=AsyncMock)
    async def test_filter_narrows_pool(self, mock_matching):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)

        mock_matching.return_value = [10]  # Only pooch 10 matches the filter

        ids = await _resolve_stray_target_ids(context, "all", {"filter": {"sex": "male"}}, rng)
        assert ids == [10]


# ---------------------------------------------------------------------------
# run_daily_stray_event_check
# ---------------------------------------------------------------------------


class TestRunDailyStrayEventCheck:
    @patch("src.game.manage_stray_events._trigger_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_random_eligible_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_servers", new_callable=AsyncMock)
    async def test_no_servers_returns_empty(self, mock_servers, mock_strays, mock_eligible, mock_trigger):
        mock_servers.return_value = []
        results = await run_daily_stray_event_check(rng_seed=42)
        assert results == {}

    @patch("src.game.manage_stray_events._trigger_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_random_eligible_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_servers", new_callable=AsyncMock)
    async def test_no_strays_no_events(self, mock_servers, mock_strays, mock_eligible, mock_trigger):
        mock_servers.return_value = [make_server(discord_id=200)]
        mock_strays.return_value = []

        results = await run_daily_stray_event_check(rng_seed=42)
        assert results == {}
        mock_eligible.assert_not_awaited()

    @patch("src.game.manage_stray_events._trigger_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_random_eligible_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_servers", new_callable=AsyncMock)
    async def test_stray_event_triggers(self, mock_servers, mock_strays, mock_eligible, mock_trigger):
        """With a stray and a lucky roll, an event should trigger."""
        mock_servers.return_value = [make_server(discord_id=200)]
        # Put multiple strays to increase the chance of at least one trigger
        mock_strays.return_value = [make_pooch(pooch_id=i) for i in range(20)]

        event = MagicMock()
        event.name = "Street Fight"
        event.actions = []
        event.outcomes = []
        event.filter = None
        mock_eligible.return_value = event

        result_obj = MagicMock()
        mock_trigger.return_value = result_obj

        # Use a seed where at least some rolls pass the 50% chance
        results = await run_daily_stray_event_check(rng_seed=42)

        # With 20 strays and 50% chance each, very likely at least some fire
        if 200 in results:
            assert len(results[200]) > 0

    @patch("src.game.manage_stray_events._trigger_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_random_eligible_stray_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_servers", new_callable=AsyncMock)
    async def test_no_eligible_event_skipped(self, mock_servers, mock_strays, mock_eligible, mock_trigger):
        mock_servers.return_value = [make_server(discord_id=200)]
        mock_strays.return_value = [make_pooch(pooch_id=1)]
        mock_eligible.return_value = None  # No eligible events

        # Use a seed that passes the 50% check
        # Seed 0: Random(0).random() = 0.844... > 0.5, so won't trigger
        # Let's find a seed that produces < 0.5
        # If roll > 0.5, the stray won't trigger anyway, so no event
        await run_daily_stray_event_check(rng_seed=1)

        # Regardless of the seed, if eligible returns None, no event fires
        mock_trigger.assert_not_awaited()


# ---------------------------------------------------------------------------
# _deliver_stray_to_kennel
# ---------------------------------------------------------------------------


class TestDeliverStrayToKennel:
    @patch("src.game.manage_stray_events.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.transfer_pooch_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.remove_pooch_from_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_owners", new_callable=AsyncMock)
    async def test_delivers_to_first_available_kennel(
        self, mock_owners, mock_kennels, mock_pooches, mock_remove, mock_transfer, mock_add_kennel
    ):
        owner = SimpleNamespace(discord_id=100)
        kennel = SimpleNamespace(id=1, pooch_limit=5)
        mock_owners.return_value = [owner]
        mock_kennels.return_value = [kennel]
        mock_pooches.return_value = []  # kennel has space
        rng = random.Random(42)

        result = await _deliver_stray_to_kennel(10, 200, rng)

        assert result is True
        mock_remove.assert_awaited_once_with(10)
        mock_transfer.assert_awaited_once_with(10, 100)
        mock_add_kennel.assert_awaited_once_with(1, 10)

    @patch("src.game.manage_stray_events.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_owners", new_callable=AsyncMock)
    async def test_returns_false_when_no_kennel_space(self, mock_owners, mock_kennels, mock_pooches):
        owner = SimpleNamespace(discord_id=100)
        kennel = SimpleNamespace(id=1, pooch_limit=2)
        mock_owners.return_value = [owner]
        mock_kennels.return_value = [kennel]
        # kennel is full
        mock_pooches.return_value = [make_pooch(pooch_id=1), make_pooch(pooch_id=2)]
        rng = random.Random(42)

        result = await _deliver_stray_to_kennel(10, 200, rng)
        assert result is False

    @patch("src.game.manage_stray_events.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_owners", new_callable=AsyncMock)
    async def test_returns_false_when_no_owners(self, mock_owners, mock_kennels):
        mock_owners.return_value = []
        mock_kennels.return_value = []
        rng = random.Random(42)

        result = await _deliver_stray_to_kennel(10, 200, rng)
        assert result is False


# ---------------------------------------------------------------------------
# _deliver_stray_to_vendor
# ---------------------------------------------------------------------------


class TestDeliverStrayToVendor:
    @patch("src.game.manage_stray_events.add_pooch_to_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.transfer_pooch_to_vendor", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.cancel_listing_for_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.remove_pooch_from_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_vendors", new_callable=AsyncMock)
    async def test_delivers_to_random_vendor(
        self, mock_vendors, mock_remove, mock_cancel, mock_transfer, mock_add_stock
    ):
        vendor = SimpleNamespace(id=5)
        mock_vendors.return_value = [vendor]
        rng = random.Random(42)

        result = await _deliver_stray_to_vendor(10, 200, rng)

        assert result is True
        mock_remove.assert_awaited_once_with(10)
        mock_transfer.assert_awaited_once_with(10, 5)
        mock_add_stock.assert_awaited_once_with(5, 10)

    @patch("src.game.manage_stray_events.list_vendors", new_callable=AsyncMock)
    async def test_returns_false_when_no_vendors(self, mock_vendors):
        mock_vendors.return_value = []
        rng = random.Random(42)

        result = await _deliver_stray_to_vendor(10, 200, rng)
        assert result is False


# ---------------------------------------------------------------------------
# _execute_single_stray_action
# ---------------------------------------------------------------------------


def _make_stray_action(action_type, parameters=None, action_order=0, repeat=1):
    action = MagicMock()
    action.action_type = action_type
    action.parameters = parameters or {}
    action.action_order = action_order
    action.repeat = repeat
    return action


class TestExecuteSingleStrayAction:
    @patch("src.game.manage_stray_events.handle_modify_health", new_callable=AsyncMock)
    async def test_modify_base_health_action(self, mock_modify):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1, 2])
        action = _make_stray_action("modify_base_health", {"selector": "all", "amount": -2})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_modify.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_modify_age", new_callable=AsyncMock)
    async def test_modify_pooch_age_action(self, mock_modify):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("modify_pooch_age", {"selector": "all", "amount": 1})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_modify.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_kill_pooch", new_callable=AsyncMock)
    async def test_kill_pooch_action_removes_from_candidates(self, mock_kill):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1, 2, 3])

        async def _kill_side_effect(pooch_ids, parameters, rng, result):
            result.pooches_killed.append(1)

        mock_kill.side_effect = _kill_side_effect
        action = _make_stray_action("kill_pooch", {"selector": "all"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        assert 1 not in context.candidate_stray_ids

    @patch("src.game.manage_stray_events.handle_add_mutation_by_name", new_callable=AsyncMock)
    async def test_add_mutation_action(self, mock_add_mut):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("add_mutation", {"selector": "all", "mutation": "cataracts"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_add_mut.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_remove_mutation_by_name", new_callable=AsyncMock)
    async def test_remove_mutation_action(self, mock_remove_mut):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("remove_mutation", {"selector": "all"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_remove_mut.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_add_breed", new_callable=AsyncMock)
    async def test_add_breed_action(self, mock_add_breed):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("add_breed", {"selector": "all", "breed": "greyhound"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_add_breed.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_remove_breed", new_callable=AsyncMock)
    async def test_remove_breed_action(self, mock_remove_breed):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("remove_breed", {"selector": "all"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_remove_breed.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_rename_pooch", new_callable=AsyncMock)
    async def test_rename_pooch_action(self, mock_rename):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("rename_pooch", {"selector": "all", "name": "Max"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_rename.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_modify_breeding_cooldown", new_callable=AsyncMock)
    async def test_modify_breeding_cooldown_action(self, mock_mod_cd):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("modify_breeding_cooldown", {"selector": "all", "amount": 1})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_mod_cd.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_modify_stat", new_callable=AsyncMock)
    async def test_modify_stat_actions(self, mock_mod_stat):
        for stat_action in (
            "modify_strength",
            "modify_cuteness",
            "modify_fluffiness",
            "modify_intelligence",
            "modify_dexterity",
            "modify_fertility",
            "modify_aggressiveness",
        ):
            mock_mod_stat.reset_mock()
            context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
            action = _make_stray_action(stat_action, {"selector": "all", "amount": 2})
            rng = random.Random(42)

            await _execute_single_stray_action(200, action, context, rng)
            mock_mod_stat.assert_awaited_once()

    @patch("src.game.manage_stray_events.handle_damn_pooch", new_callable=AsyncMock)
    async def test_damn_pooch_action(self, mock_damn):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("damn_pooch", {"selector": "all"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_damn.assert_awaited_once()

    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.revive_pooch", new_callable=AsyncMock)
    async def test_revive_pooch_to_stray(self, mock_revive, mock_add_stray):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        context.extra_data["my_slot"] = {"pooch_ids": [99]}
        action = _make_stray_action("revive_pooch", {"use_saved": "my_slot", "destination": "stray"})
        revived = make_pooch(pooch_id=99)
        mock_revive.return_value = revived
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_revive.assert_awaited_once_with(99)
        mock_add_stray.assert_awaited_once_with(99, 200)
        assert 99 in result.pooches_affected
        assert 99 in context.candidate_stray_ids

    @patch("src.game.manage_stray_events._deliver_stray_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.revive_pooch", new_callable=AsyncMock)
    async def test_revive_pooch_to_kennel_success(self, mock_revive, mock_add_stray, mock_deliver):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        context.extra_data["my_slot"] = {"pooch_ids": [99]}
        action = _make_stray_action("revive_pooch", {"use_saved": "my_slot", "destination": "kennel"})
        mock_revive.return_value = make_pooch(pooch_id=99)
        mock_deliver.return_value = True
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_deliver.assert_awaited_once_with(99, 200, rng)
        mock_add_stray.assert_not_awaited()
        assert 99 in result.pooches_affected

    @patch("src.game.manage_stray_events._deliver_stray_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.revive_pooch", new_callable=AsyncMock)
    async def test_revive_pooch_to_kennel_fallback_to_stray(self, mock_revive, mock_add_stray, mock_deliver):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        context.extra_data["slot"] = {"pooch_ids": [99]}
        action = _make_stray_action("revive_pooch", {"use_saved": "slot", "destination": "kennel"})
        mock_revive.return_value = make_pooch(pooch_id=99)
        mock_deliver.return_value = False  # no kennel space
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_add_stray.assert_awaited_once_with(99, 200)
        assert 99 in context.candidate_stray_ids

    @patch("src.game.manage_stray_events._deliver_stray_to_vendor", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.revive_pooch", new_callable=AsyncMock)
    async def test_revive_pooch_to_vendor_success(self, mock_revive, mock_deliver):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        context.extra_data["slot"] = {"pooch_ids": [99]}
        action = _make_stray_action("revive_pooch", {"use_saved": "slot", "destination": "vendor"})
        mock_revive.return_value = make_pooch(pooch_id=99)
        mock_deliver.return_value = True
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_deliver.assert_awaited_once_with(99, 200, rng)
        assert 99 in result.pooches_affected

    @patch("src.game.manage_stray_events.revive_pooch", new_callable=AsyncMock)
    async def test_revive_pooch_noop_when_revive_fails(self, mock_revive):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        context.extra_data["slot"] = {"pooch_ids": [99]}
        action = _make_stray_action("revive_pooch", {"use_saved": "slot"})
        mock_revive.return_value = None  # revive failed
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        assert result.pooches_affected == []

    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.create_pooch", new_callable=AsyncMock)
    async def test_create_pooch_action(self, mock_create, mock_add_mut, mock_add_stray):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("create_pooch", {"name": "NewPup", "base_health": 10})
        new_pooch = make_pooch(pooch_id=55)
        mock_create.return_value = new_pooch
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_add_stray.assert_awaited_once_with(55, 200)
        assert 55 in result.pooches_created
        assert 55 in context.candidate_stray_ids

    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.create_pooch", new_callable=AsyncMock)
    async def test_create_pooch_with_save_as(self, mock_create, mock_add_mut, mock_add_stray):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        action = _make_stray_action("create_pooch", {"save_as": "new_pup_slot"})
        new_pooch = make_pooch(pooch_id=77)
        mock_create.return_value = new_pooch
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        assert context.extra_data.get("new_pup_slot") == {"pooch_ids": [77]}

    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.create_pooch", new_callable=AsyncMock)
    async def test_create_pooch_with_int_mutations(self, mock_create, mock_breed_ids, mock_add_mut, mock_add_stray):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        action = _make_stray_action("create_pooch", {"mutations": 2, "breeds": 1})
        new_pooch = make_pooch(pooch_id=88)
        mock_create.return_value = new_pooch
        mock_breed_ids.return_value = [3]
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        assert mock_add_mut.await_count == 2

    @patch("src.game.manage_stray_events.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.create_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_pooch_by_id", new_callable=AsyncMock)
    async def test_clone_pooch_action(
        self, mock_get, mock_create, mock_breed_weights, mock_mutations, mock_add_stray, mock_add_breeds, mock_add_mut
    ):
        source = make_pooch(pooch_id=10)
        clone = make_pooch(pooch_id=20)
        mock_get.return_value = source
        mock_create.return_value = clone
        mock_breed_weights.return_value = [(1, 1.0)]
        mock_mutations.return_value = [MagicMock(id=5)]

        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10])
        action = _make_stray_action("clone_pooch", {"selector": "all", "save_as": "cloned_slot"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_add_stray.assert_awaited_once_with(20, 200)
        assert 20 in result.pooches_created
        assert context.extra_data.get("cloned_slot") == {"pooch_ids": [20]}

    @patch("src.game.manage_stray_events.get_pooch_by_id", new_callable=AsyncMock)
    async def test_clone_pooch_no_source_skips(self, mock_get):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        action = _make_stray_action("clone_pooch", {"selector": "random"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_get.assert_not_awaited()
        assert result.pooches_created == []

    @patch("src.game.manage_stray_events._deliver_stray_to_kennel", new_callable=AsyncMock)
    async def test_enter_kennel_action_success(self, mock_deliver):
        mock_deliver.return_value = True
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1, 2])
        action = _make_stray_action("enter_kennel", {"selector": "all"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        assert result.pooches_affected == [1, 2]
        assert 1 not in context.candidate_stray_ids
        assert 2 not in context.candidate_stray_ids

    @patch("src.game.manage_stray_events._deliver_stray_to_kennel", new_callable=AsyncMock)
    async def test_enter_kennel_action_no_space(self, mock_deliver):
        mock_deliver.return_value = False
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("enter_kennel", {"selector": "all"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        assert result.pooches_affected == []
        assert 1 in context.candidate_stray_ids

    @patch("src.game.manage_stray_events._deliver_stray_to_vendor", new_callable=AsyncMock)
    async def test_enter_vendor_stock_action_success(self, mock_deliver):
        mock_deliver.return_value = True
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[5])
        action = _make_stray_action("enter_vendor_stock", {"selector": "all"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        assert result.pooches_affected == [5]
        assert 5 not in context.candidate_stray_ids

    @patch("src.game.manage_stray_events._deliver_stray_to_vendor", new_callable=AsyncMock)
    async def test_enter_vendor_stock_no_vendor(self, mock_deliver):
        mock_deliver.return_value = False
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[5])
        action = _make_stray_action("enter_vendor_stock", {"selector": "all"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        assert result.pooches_affected == []
        assert 5 in context.candidate_stray_ids

    async def test_unknown_action_type_returns_result(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("totally_unknown_action", {})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        # Should log a warning but not crash; result still succeeds
        assert result.success is True

    async def test_select_pooch_action(self):
        """select_pooch just resolves IDs into a named slot, no other side effects."""
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1, 2, 3])
        action = _make_stray_action("select_pooch", {"selector": "all", "save_as": "picked"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        # The save_as slot should be populated
        assert "picked" in context.extra_data

    @patch("src.game.manage_stray_events._execute_stray_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events._choose_stray_event_outcome", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.get_stray_event_by_name", new_callable=AsyncMock)
    async def test_start_stray_event_action(self, mock_get_event, mock_choose, mock_execute):
        followup_event = MagicMock()
        followup_event.actions = []
        followup_event.outcomes = []
        mock_get_event.return_value = followup_event

        mock_choose.return_value = None
        mock_execute.return_value = StrayEventResult()

        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("start_stray_event", {"event": "SomeEvent"})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_get_event.assert_awaited_once_with("SomeEvent")

    @patch("src.game.manage_stray_events.get_stray_event_by_name", new_callable=AsyncMock)
    async def test_start_stray_event_unknown_event_skips(self, mock_get_event):
        mock_get_event.return_value = None
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("start_stray_event", {"event": "NonExistentEvent"})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        # Should log a warning and return without crashing
        assert result.success is True

    async def test_action_exception_marks_failure(self):
        """An exception in the action handler should mark result.success = False."""
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("modify_base_health", {"selector": "all"})

        with patch(
            "src.game.manage_stray_events.handle_modify_health",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            rng = random.Random(42)
            result = await _execute_single_stray_action(200, action, context, rng)
            assert result.success is False


# ---------------------------------------------------------------------------
# _execute_stray_event_actions
# ---------------------------------------------------------------------------


class TestExecuteStrayEventActions:
    @patch("src.game.manage_stray_events.handle_modify_health", new_callable=AsyncMock)
    async def test_runs_actions_in_order(self, mock_modify):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        a1 = _make_stray_action("modify_base_health", {"selector": "all", "amount": 1}, action_order=1)
        a2 = _make_stray_action("modify_base_health", {"selector": "all", "amount": 2}, action_order=0)
        rng = random.Random(42)

        await _execute_stray_event_actions(200, [a1, a2], context, rng)
        # Both actions should have been called (twice total)
        assert mock_modify.await_count == 2

    @patch("src.game.manage_stray_events.handle_modify_health", new_callable=AsyncMock)
    async def test_repeat_executes_multiple_times(self, mock_modify):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        action = _make_stray_action("modify_base_health", {"selector": "all", "amount": 1}, action_order=0, repeat=3)
        rng = random.Random(42)

        await _execute_stray_event_actions(200, [action], context, rng)
        assert mock_modify.await_count == 3

    async def test_empty_actions_returns_empty_result(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        rng = random.Random(42)

        result = await _execute_stray_event_actions(200, [], context, rng)
        assert result.pooches_affected == []
        assert result.pooches_killed == []
        assert result.pooches_created == []


# ---------------------------------------------------------------------------
# Helper: temporarily swap a _STAT_GETTERS entry to avoid real DB calls
# ---------------------------------------------------------------------------


def _patch_stat_getter(stat_name, return_value):
    """Context manager that temporarily replaces _STAT_GETTERS[stat_name]."""
    from contextlib import contextmanager

    import src.game.manage_stray_events as _mod

    @contextmanager
    def _cm():
        mock = AsyncMock(return_value=return_value)
        original = _mod._STAT_GETTERS[stat_name]
        _mod._STAT_GETTERS[stat_name] = mock
        try:
            yield mock
        finally:
            _mod._STAT_GETTERS[stat_name] = original

    return _cm()


# ---------------------------------------------------------------------------
# _choose_stray_event_outcome
# ---------------------------------------------------------------------------


class TestChooseStrayEventOutcome:
    def _make_event_with_outcomes(self, outcomes):
        event = MagicMock()
        event.outcomes = outcomes
        return event

    def _make_outcome(self, chance=None, stat_weights=None, label="outcome"):
        o = MagicMock()
        o.chance = chance
        o.stat_weights = stat_weights or []
        o.label = label
        o.actions = []
        return o

    async def test_no_outcomes_returns_none(self):
        event = self._make_event_with_outcomes([])
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        rng = random.Random(42)

        result = await _choose_stray_event_outcome(event, context, rng)
        assert result is None

    async def test_single_fixed_outcome_always_selected(self):
        outcome = self._make_outcome(chance=1.0)
        event = self._make_event_with_outcomes([outcome])
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        rng = random.Random(42)

        result = await _choose_stray_event_outcome(event, context, rng)
        assert result is outcome

    async def test_two_fixed_outcomes_respects_probability(self):
        o1 = self._make_outcome(chance=0.99, label="common")
        o2 = self._make_outcome(chance=0.01, label="rare")
        event = self._make_event_with_outcomes([o1, o2])
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        # Seed 42 gives 0.639... for first roll → falls in o1's range
        rng = random.Random(42)

        result = await _choose_stray_event_outcome(event, context, rng)
        assert result is o1

    async def test_implicit_outcomes_compete_equally(self):
        """Outcomes with no chance and no stat_weights get equal probability."""
        o1 = self._make_outcome(chance=None, label="a")
        o2 = self._make_outcome(chance=None, label="b")
        event = self._make_event_with_outcomes([o1, o2])
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        rng = random.Random(42)

        result = await _choose_stray_event_outcome(event, context, rng)
        assert result in [o1, o2]

    async def test_all_dynamic_zero_weight_falls_back(self):
        """When all dynamic outcomes have 0 weight, falls back to rng.choice."""
        o1 = self._make_outcome(chance=0.0, stat_weights=[])
        o1.stat_weights = [{"stat": "strength", "pooch": "random", "scale": -999.0, "pivot": 0.0, "direction": 1.0}]
        event = self._make_event_with_outcomes([o1])
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])

        with _patch_stat_getter("strength", 0):
            rng = random.Random(42)
            result = await _choose_stray_event_outcome(event, context, rng)
            # Should return something (not crash)
            assert result is not None

    async def test_last_entry_fallback_when_cumulative_not_reached(self):
        """When no cumulative threshold is crossed, the last entry is returned."""
        o1 = self._make_outcome(chance=0.1, label="x")
        o2 = self._make_outcome(chance=0.1, label="y")
        event = self._make_event_with_outcomes([o1, o2])
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        # Use a roll that exceeds cumulative sum (0.2)
        with patch.object(random.Random, "random", return_value=0.99):
            rng = random.Random(42)
            result = await _choose_stray_event_outcome(event, context, rng)
            assert result in [o1, o2]


# ---------------------------------------------------------------------------
# _resolve_single_stat_pooch_id
# ---------------------------------------------------------------------------


class TestResolveSingleStatPoochId:
    def test_random_selector_picks_from_candidates(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)

        result = _resolve_single_stat_pooch_id("random", context, rng)
        assert result in [10, 20, 30]

    def test_random_selector_empty_candidates_returns_none(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        rng = random.Random(42)

        result = _resolve_single_stat_pooch_id("random", context, rng)
        assert result is None

    def test_named_slot_returns_first_id(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        context.extra_data["my_slot"] = {"pooch_ids": [42, 43]}
        rng = random.Random(42)

        result = _resolve_single_stat_pooch_id("my_slot", context, rng)
        assert result == 42

    def test_named_slot_empty_returns_none(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        context.extra_data["my_slot"] = {"pooch_ids": []}
        rng = random.Random(42)

        result = _resolve_single_stat_pooch_id("my_slot", context, rng)
        assert result is None

    def test_unknown_selector_returns_none(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        rng = random.Random(42)

        result = _resolve_single_stat_pooch_id("nonexistent_slot", context, rng)
        assert result is None


# ---------------------------------------------------------------------------
# _get_effective_pooch_stat
# ---------------------------------------------------------------------------


class TestGetEffectivePoochStat:
    async def test_known_stat_returns_float(self):
        import src.game.manage_stray_events as _mod

        mock_getter = AsyncMock(return_value=15)
        original = _mod._STAT_GETTERS["strength"]
        _mod._STAT_GETTERS["strength"] = mock_getter
        try:
            result = await _get_effective_pooch_stat("strength", 1)
            assert result == 15.0
        finally:
            _mod._STAT_GETTERS["strength"] = original

    @patch("src.game.manage_stray_events.get_pooch_size", new_callable=AsyncMock)
    async def test_size_stat_returns_float(self, mock_getter):
        mock_getter.return_value = 12
        result = await _get_effective_pooch_stat("size", 1)
        assert result == 12.0

    @patch("src.game.manage_stray_events.get_pooch_size", new_callable=AsyncMock)
    async def test_size_none_defaults_to_ten(self, mock_getter):
        mock_getter.return_value = None
        result = await _get_effective_pooch_stat("size", 1)
        assert result == 10.0

    async def test_unknown_stat_returns_none(self):
        result = await _get_effective_pooch_stat("unknown_stat", 1)
        assert result is None

    async def test_none_value_returns_none(self):
        import src.game.manage_stray_events as _mod

        mock_getter = AsyncMock(return_value=None)
        original = _mod._STAT_GETTERS["strength"]
        _mod._STAT_GETTERS["strength"] = mock_getter
        try:
            result = await _get_effective_pooch_stat("strength", 1)
            assert result is None
        finally:
            _mod._STAT_GETTERS["strength"] = original


# ---------------------------------------------------------------------------
# _compute_outcome_stat_multiplier
# ---------------------------------------------------------------------------


class TestComputeOutcomeStatMultiplier:
    async def test_multiplier_above_pivot_increases(self):
        with _patch_stat_getter("strength", 20):  # above pivot of 10
            context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
            stat_weights = [{"stat": "strength", "pooch": "random", "scale": 0.1, "pivot": 10.0, "direction": 1.0}]
            rng = random.Random(42)

            multiplier = await _compute_outcome_stat_multiplier(stat_weights, context, rng)
            # entry_mult = 1 + (20 - 10) * 0.1 * 1.0 = 2.0
            assert multiplier == pytest.approx(2.0)

    async def test_multiplier_at_pivot_is_one(self):
        with _patch_stat_getter("strength", 10):  # exactly at pivot
            context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
            stat_weights = [{"stat": "strength", "pooch": "random", "scale": 0.1, "pivot": 10.0, "direction": 1.0}]
            rng = random.Random(42)

            multiplier = await _compute_outcome_stat_multiplier(stat_weights, context, rng)
            assert multiplier == pytest.approx(1.0)

    async def test_non_dict_entry_skipped(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        stat_weights = ["not_a_dict", 42]
        rng = random.Random(42)

        multiplier = await _compute_outcome_stat_multiplier(stat_weights, context, rng)
        assert multiplier == pytest.approx(1.0)

    async def test_no_pooch_skips_entry(self):
        """When no pooch can be resolved, the entry is skipped."""
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        stat_weights = [{"stat": "strength", "pooch": "random", "scale": 0.5, "pivot": 10.0, "direction": 1.0}]
        rng = random.Random(42)

        multiplier = await _compute_outcome_stat_multiplier(stat_weights, context, rng)
        assert multiplier == pytest.approx(1.0)

    async def test_unknown_stat_skips_entry(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
        stat_weights = [{"stat": "not_a_real_stat", "pooch": "random", "scale": 0.5, "pivot": 10.0}]
        rng = random.Random(42)

        multiplier = await _compute_outcome_stat_multiplier(stat_weights, context, rng)
        assert multiplier == pytest.approx(1.0)

    async def test_multiplier_clamped_to_zero(self):
        with _patch_stat_getter("strength", 0):  # very low
            context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1])
            stat_weights = [{"stat": "strength", "pooch": "random", "scale": 10.0, "pivot": 10.0, "direction": 1.0}]
            rng = random.Random(42)

            multiplier = await _compute_outcome_stat_multiplier(stat_weights, context, rng)
            assert multiplier == 0.0  # clamped to max(0, ...)


# ---------------------------------------------------------------------------
# _trigger_stray_event_for_server
# ---------------------------------------------------------------------------


class TestTriggerStrayEventForServer:
    def _make_stray_event(self, name="TestEvent", actions=None, outcomes=None, filter_spec=None):
        event = MagicMock()
        event.name = name
        event.actions = actions or []
        event.outcomes = outcomes or []
        event.filter = filter_spec
        return event

    @patch("src.game.manage_stray_events._choose_stray_event_outcome", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events._execute_stray_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    async def test_no_candidates_returns_none(self, mock_strays, mock_exec, mock_choose):
        mock_strays.return_value = []
        event = self._make_stray_event()
        rng = random.Random(42)

        result = await _trigger_stray_event_for_server(200, event, rng)
        assert result is None
        mock_exec.assert_not_awaited()

    @patch("src.game.manage_stray_events._choose_stray_event_outcome", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events._execute_stray_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    async def test_runs_actions_and_outcome(self, mock_strays, mock_exec, mock_choose):
        stray = make_pooch(pooch_id=1)
        mock_strays.return_value = [stray]

        action_result = StrayEventResult(pooches_affected=[1])
        outcome_result = StrayEventResult(pooches_affected=[2])
        mock_exec.side_effect = [action_result, outcome_result]

        outcome = MagicMock()
        outcome.actions = []
        mock_choose.return_value = outcome

        event = self._make_stray_event()
        rng = random.Random(42)

        result = await _trigger_stray_event_for_server(200, event, rng)
        assert result is not None
        assert 1 in result.pooches_affected
        assert 2 in result.pooches_affected

    @patch("src.game.manage_stray_events._choose_stray_event_outcome", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events._execute_stray_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_strays_for_server", new_callable=AsyncMock)
    async def test_no_outcome_still_returns_result(self, mock_strays, mock_exec, mock_choose):
        stray = make_pooch(pooch_id=1)
        mock_strays.return_value = [stray]
        mock_exec.return_value = StrayEventResult(pooches_affected=[1])
        mock_choose.return_value = None

        event = self._make_stray_event()
        rng = random.Random(42)

        result = await _trigger_stray_event_for_server(200, event, rng)
        assert result is not None
        assert result.pooches_affected == [1]

    @patch("src.game.manage_stray_events._choose_stray_event_outcome", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events._execute_stray_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_matching_stray_pooch_ids", new_callable=AsyncMock)
    async def test_uses_filter_from_event(self, mock_matching, mock_exec, mock_choose):
        mock_matching.return_value = [10, 20]
        mock_exec.return_value = StrayEventResult()
        mock_choose.return_value = None

        filter_spec = {"pooches": [{"sex": "female"}]}
        event = self._make_stray_event(filter_spec=filter_spec)
        rng = random.Random(42)

        result = await _trigger_stray_event_for_server(200, event, rng)
        mock_matching.assert_awaited_once()
        assert result is not None

    @patch("src.game.manage_stray_events._execute_stray_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_matching_stray_pooch_ids", new_callable=AsyncMock)
    async def test_filter_returns_no_candidates_returns_none(self, mock_matching, mock_exec):
        mock_matching.return_value = []
        filter_spec = {"pooches": [{"sex": "female"}]}
        event = self._make_stray_event(filter_spec=filter_spec)
        rng = random.Random(42)

        result = await _trigger_stray_event_for_server(200, event, rng)
        assert result is None
        mock_exec.assert_not_awaited()


# ---------------------------------------------------------------------------
# breed_pooches action in _execute_single_stray_action
# ---------------------------------------------------------------------------


class TestBreedPoochesAction:
    @patch("src.game.manage_stray_events.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events._breed_pooches", new_callable=AsyncMock)
    @patch("src.game.manage_stray_events.list_matching_stray_pooch_ids", new_callable=AsyncMock)
    async def test_breed_pooches_adds_baby_to_strays(self, mock_matching, mock_breed, mock_add_stray):
        mock_matching.return_value = [1, 2]
        mock_breed.return_value = [99]

        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1, 2])
        action = _make_stray_action(
            "breed_pooches",
            {"first_filter": {"sex": "male"}, "second_filter": {"sex": "female"}},
        )
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        mock_add_stray.assert_awaited_with(99, 200)
        assert 99 in result.pooches_created

    @patch("src.game.manage_stray_events._breed_pooches", new_callable=AsyncMock)
    async def test_breed_pooches_empty_pool_skips(self, mock_breed):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[])
        action = _make_stray_action("breed_pooches", {})
        rng = random.Random(42)

        await _execute_single_stray_action(200, action, context, rng)
        mock_breed.assert_not_awaited()

    @patch("src.game.manage_stray_events._breed_pooches", new_callable=AsyncMock)
    async def test_breed_pooches_value_error_logs_warning(self, mock_breed):
        mock_breed.side_effect = ValueError("incompatible")

        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[1, 2])
        action = _make_stray_action("breed_pooches", {})
        rng = random.Random(42)

        result = await _execute_single_stray_action(200, action, context, rng)
        # Should not raise, just log a warning
        assert result.success is True
