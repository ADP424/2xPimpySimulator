"""Tests for src/game/manage_server_events.py — trigger, participate, resolve."""

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import make_kennel, make_server


@pytest.fixture(autouse=True)
def mock_server_events_db_calls():
    """Auto-patch get_current_season so tests never hit the real DB."""
    with patch("src.game.manage_server_events.get_current_season", new=AsyncMock(return_value="spring")):
        yield


from src.game.manage_server_events import (
    _aggregate_player_score,
    _build_owner_event_context,
    _matches_rank,
    _roll_outcome_chance,
    get_active_server_event,
    list_active_server_events,
    participate_in_server_event,
    resolve_server_event,
    run_daily_server_event_cycle,
    set_server_event_message_id,
    trigger_daily_server_event,
)

# ---------------------------------------------------------------------------
# _roll_outcome_chance
# ---------------------------------------------------------------------------


class TestRollOutcomeChance:
    def test_none_chance_always_true(self):
        assert _roll_outcome_chance(None, random.Random(42)) is True

    def test_zero_chance_always_false(self):
        rng = random.Random(42)
        assert _roll_outcome_chance(0.0, rng) is False

    def test_one_chance_always_true(self):
        assert _roll_outcome_chance(1.0, random.Random(42)) is True

    def test_deterministic_with_seed(self):
        r1 = _roll_outcome_chance(0.5, random.Random(42))
        r2 = _roll_outcome_chance(0.5, random.Random(42))
        assert r1 == r2


# ---------------------------------------------------------------------------
# _matches_rank
# ---------------------------------------------------------------------------


class TestMatchesRank:
    def test_no_constraints(self):
        assert _matches_rank(None, None, 1) is True

    def test_min_rank_only(self):
        assert _matches_rank(2, None, 1) is False
        assert _matches_rank(2, None, 2) is True
        assert _matches_rank(2, None, 3) is True

    def test_max_rank_only(self):
        assert _matches_rank(None, 3, 4) is False
        assert _matches_rank(None, 3, 3) is True
        assert _matches_rank(None, 3, 1) is True

    def test_both_min_and_max(self):
        assert _matches_rank(2, 4, 1) is False
        assert _matches_rank(2, 4, 2) is True
        assert _matches_rank(2, 4, 4) is True
        assert _matches_rank(2, 4, 5) is False

    def test_none_rank_matches_only_when_no_constraints(self):
        assert _matches_rank(None, None, None) is True
        assert _matches_rank(1, None, None) is False
        assert _matches_rank(None, 3, None) is False


# ---------------------------------------------------------------------------
# _aggregate_player_score
# ---------------------------------------------------------------------------


class TestAggregatePlayerScore:
    def test_sum(self):
        assert _aggregate_player_score([1.0, 2.0, 3.0], "sum") == 6.0

    def test_average(self):
        assert _aggregate_player_score([2.0, 4.0], "average") == 3.0

    def test_max(self):
        assert _aggregate_player_score([1.0, 5.0, 3.0], "max") == 5.0

    def test_empty_returns_zero(self):
        assert _aggregate_player_score([], "sum") == 0.0

    def test_unknown_aggregate_defaults_to_sum(self):
        assert _aggregate_player_score([1.0, 2.0], "unknown") == 3.0


# ---------------------------------------------------------------------------
# trigger_daily_server_event
# ---------------------------------------------------------------------------


class TestTriggerDailyServerEvent:
    @patch("src.game.manage_server_events.to_triggered_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence_by_tier", new_callable=AsyncMock)
    async def test_returns_existing_event_if_active(self, mock_existing, mock_to_event):
        occurrence = MagicMock()
        mock_existing.return_value = occurrence
        expected = SimpleNamespace(name="Existing")
        mock_to_event.return_value = expected

        result = await trigger_daily_server_event(200)
        assert result.name == "Existing"

    @patch("src.game.manage_server_events.get_server_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence_by_tier", new_callable=AsyncMock)
    async def test_returns_none_if_no_event_channel(self, mock_existing, mock_server):
        mock_existing.return_value = None
        mock_server.return_value = make_server(discord_id=200, event_channel_discord_id=None)

        result = await trigger_daily_server_event(200)
        assert result is None

    @patch("src.game.manage_server_events.get_server_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence_by_tier", new_callable=AsyncMock)
    async def test_returns_none_if_server_not_found(self, mock_existing, mock_server):
        mock_existing.return_value = None
        mock_server.return_value = None

        result = await trigger_daily_server_event(200)
        assert result is None

    @patch("src.game.manage_server_events.to_triggered_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.create_server_event_occurrence", new_callable=AsyncMock)
    @patch("src.game.manage_server_events._check_server_filter", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_server_events_with_weights_by_tier", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence_by_tier", new_callable=AsyncMock)
    async def test_triggers_new_event(
        self, mock_existing, mock_server, mock_eligible, mock_filter, mock_create, mock_get_occ, mock_to_event
    ):
        mock_existing.return_value = None
        mock_server.return_value = make_server(discord_id=200, event_channel_discord_id=12345)

        event = MagicMock()
        event.id = 1
        event.name = "Town Raffle"
        event.filter = {}
        event.actions = []
        mock_eligible.return_value = [(event, 1)]
        mock_filter.return_value = True

        occurrence = SimpleNamespace(id=10)
        mock_create.return_value = occurrence

        hydrated = MagicMock()
        mock_get_occ.return_value = hydrated

        expected = SimpleNamespace(name="Town Raffle")
        mock_to_event.return_value = expected

        result = await trigger_daily_server_event(200)
        assert result.name == "Town Raffle"


# ---------------------------------------------------------------------------
# participate_in_server_event
# ---------------------------------------------------------------------------


class TestParticipateInServerEvent:
    def _make_occurrence(self, archived=False, resolved_at=None, expired=False, participations=None, event_id=1):
        occ = MagicMock()
        occ.server_discord_id = 200
        occ.archived = archived
        occ.resolved_at = resolved_at
        occ.expires_at = datetime.now(timezone.utc) + (timedelta(days=-1) if expired else timedelta(days=1))
        occ.server_event_id = event_id
        occ.server_event = MagicMock()
        occ.server_event.name = "Test Event"
        occ.participations = participations or []
        return occ

    def _make_menu_option(self, option_id=1, menu_server_event_id=1, actions=None):
        opt = MagicMock()
        opt.id = option_id
        opt.label = "Enter"
        opt.filter = {}
        opt.requires = {}
        opt.scoring = {}
        opt.actions = actions or []
        menu = MagicMock()
        menu.name = "enter"
        menu.label = "Enter"
        menu.depends_on = []
        menu.max_uses_per_player = 1
        menu.server_event_id = menu_server_event_id
        opt.menu = menu
        return opt

    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_occurrence_not_found(self, mock_get_occ):
        mock_get_occ.return_value = None
        ok, msg, summary = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "not found" in msg.lower()

    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_already_resolved(self, mock_get_occ):
        mock_get_occ.return_value = self._make_occurrence(resolved_at=datetime.now(timezone.utc))
        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "resolved" in msg.lower()

    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_event_expired(self, mock_get_occ):
        mock_get_occ.return_value = self._make_occurrence(expired=True)
        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "expired" in msg.lower()

    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_owner_not_registered(self, mock_get_occ, mock_create_owner, mock_owner_server):
        mock_get_occ.return_value = self._make_occurrence()
        mock_owner_server.return_value = None
        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "registered" in msg.lower()

    @patch("src.game.manage_server_events.get_server_event_menu_option_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_participation", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_invalid_option(
        self, mock_get_occ, mock_create_owner, mock_owner_server, mock_existing_part, mock_option
    ):
        mock_get_occ.return_value = self._make_occurrence()
        mock_owner_server.return_value = MagicMock()
        mock_existing_part.return_value = None
        mock_option.return_value = None
        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "not valid" in msg.lower()


# ---------------------------------------------------------------------------
# resolve_server_event
# ---------------------------------------------------------------------------


class TestResolveServerEvent:
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_resolve_returns_none_if_not_found(self, mock_get):
        mock_get.return_value = None
        result = await resolve_server_event(1)
        assert result is None

    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_resolve_returns_none_if_already_resolved(self, mock_get):
        occ = MagicMock()
        occ.archived = False
        occ.resolved_at = datetime.now(timezone.utc)
        mock_get.return_value = occ

        result = await resolve_server_event(1)
        assert result is None

    @patch("src.game.manage_server_events.resolve_server_event_occurrence", new_callable=AsyncMock)
    @patch("src.game.manage_server_events._rank_participations", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_resolve_with_no_participants_fires_default_actions(self, mock_get, mock_rank, mock_resolve):
        occ = MagicMock()
        occ.id = 1
        occ.archived = False
        occ.resolved_at = None
        occ.server_discord_id = 200
        occ.context = {}
        occ.server_event = MagicMock()
        occ.server_event.name = "Test"
        occ.server_event.outcomes = []
        occ.server_event.default_actions_data = []
        occ.participations = []
        mock_get.return_value = occ
        mock_rank.return_value = []

        result = await resolve_server_event(1)

        assert result is not None
        assert result.participant_count == 0
        assert result.winner_owner_ids == []


# ---------------------------------------------------------------------------
# _build_owner_event_context
# ---------------------------------------------------------------------------


class TestBuildOwnerEventContext:
    @patch("src.game.manage_server_events.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_builds_context_with_kennels_and_pooches(self, mock_kennels, mock_pooches):
        kennel = make_kennel(kennel_id=1, name="K")
        mock_kennels.return_value = [kennel]
        pooch_alive = SimpleNamespace(id=10, alive=True)
        pooch_dead = SimpleNamespace(id=11, alive=False)
        mock_pooches.return_value = [pooch_alive, pooch_dead]

        ctx = await _build_owner_event_context(100)
        assert ctx.owner_discord_id == 100
        assert ctx.extra_data["candidate_kennel_ids"] == [1]
        assert ctx.extra_data["candidate_pooch_ids"] == [10]  # dead pooch excluded

    @patch("src.game.manage_server_events.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_sets_selected_pooch_id(self, mock_kennels, mock_pooches):
        mock_kennels.return_value = []
        ctx = await _build_owner_event_context(100, selected_pooch_id=42)
        assert ctx.selected_pooch_id == 42
        assert 42 in ctx.affected_pooch_ids

    @patch("src.game.manage_server_events.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_no_selected_pooch(self, mock_kennels, mock_pooches):
        mock_kennels.return_value = []
        ctx = await _build_owner_event_context(100)
        assert ctx.selected_pooch_id is None


# ---------------------------------------------------------------------------
# get_active_server_event / list_active_server_events / set_server_event_message_id
# ---------------------------------------------------------------------------


class TestGetActiveServerEvent:
    @patch("src.game.manage_server_events.to_triggered_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence", new_callable=AsyncMock)
    async def test_returns_event_when_active(self, mock_occ, mock_to_event):
        mock_occ.return_value = MagicMock()
        expected = SimpleNamespace(name="Active")
        mock_to_event.return_value = expected
        result = await get_active_server_event(200)
        assert result.name == "Active"

    @patch("src.game.manage_server_events.get_active_server_event_occurrence", new_callable=AsyncMock)
    async def test_returns_none_when_no_active(self, mock_occ):
        mock_occ.return_value = None
        result = await get_active_server_event(200)
        assert result is None


class TestListActiveServerEvents:
    @patch("src.game.manage_server_events.to_triggered_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_active_server_event_occurrences", new_callable=AsyncMock)
    async def test_converts_occurrences(self, mock_list, mock_to_event):
        mock_list.return_value = [MagicMock(), MagicMock()]
        mock_to_event.return_value = SimpleNamespace(name="E")
        result = await list_active_server_events()
        assert len(result) == 2


class TestSetServerEventMessageId:
    @patch("src.game.manage_server_events.set_server_event_occurrence_message_discord_id", new_callable=AsyncMock)
    async def test_delegates_to_db(self, mock_set):
        await set_server_event_message_id(1, 12345)
        mock_set.assert_awaited_once_with(1, 12345)


# ---------------------------------------------------------------------------
# run_daily_server_event_cycle
# ---------------------------------------------------------------------------


class TestRunDailyServerEventCycle:
    @patch("src.game.manage_server_events.advance_season", new_callable=AsyncMock, return_value="summer")
    @patch("src.game.manage_server_events.trigger_daily_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_servers", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.resolve_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_active_server_event_occurrences", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.datetime")
    async def test_resolves_then_triggers(
        self, mock_dt, mock_active, mock_resolve, mock_servers, mock_trigger, mock_advance
    ):
        # Simulate the weekday that triggers major events (weekday() == 2)
        monday = MagicMock()
        monday.weekday.return_value = 2
        mock_dt.now.return_value = monday

        occ = MagicMock()
        occ.id = 1
        mock_active.return_value = [occ]
        resolution = MagicMock()
        mock_resolve.return_value = resolution

        server = SimpleNamespace(discord_id=200, event_channel_discord_id=12345)
        mock_servers.return_value = [server]

        new_event = SimpleNamespace(name="New")
        mock_trigger.return_value = new_event

        new_events, resolutions, season_advances = await run_daily_server_event_cycle()

        assert len(resolutions) == 1
        assert 200 in new_events
        assert season_advances == {200: "summer"}

    @patch("src.game.manage_server_events.trigger_daily_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_servers", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.resolve_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_active_server_event_occurrences", new_callable=AsyncMock)
    async def test_skips_servers_without_event_channel(self, mock_active, mock_resolve, mock_servers, mock_trigger):
        mock_active.return_value = []
        mock_resolve.return_value = None

        server_no_channel = SimpleNamespace(discord_id=300, event_channel_discord_id=None)
        mock_servers.return_value = [server_no_channel]

        new_events, resolutions, season_advances = await run_daily_server_event_cycle()
        assert len(new_events) == 0
        assert len(season_advances) == 0
        mock_trigger.assert_not_awaited()
