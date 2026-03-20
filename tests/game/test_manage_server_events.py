"""Tests for src/game/manage_server_events.py — trigger, participate, resolve."""

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_kennel, make_owner, make_server
from src.game.manage_server_events import (
    _build_owner_event_context,
    _compute_participation_score,
    _matches_rank,
    _rank_participations,
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
        """With chance=0, rng.random() is always > 0 (practically)."""
        # Very small chance it could return 0.0, but with a fixed seed we can verify
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
# trigger_daily_server_event
# ---------------------------------------------------------------------------


class TestTriggerDailyServerEvent:
    @patch("src.game.manage_server_events.to_triggered_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence", new_callable=AsyncMock)
    async def test_returns_existing_event_if_active(self, mock_existing, mock_to_event):
        occurrence = MagicMock()
        mock_existing.return_value = occurrence
        expected = SimpleNamespace(name="Existing")
        mock_to_event.return_value = expected

        result = await trigger_daily_server_event(200)
        assert result.name == "Existing"

    @patch("src.game.manage_server_events.get_server_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence", new_callable=AsyncMock)
    async def test_returns_none_if_no_event_channel(self, mock_existing, mock_server):
        mock_existing.return_value = None
        mock_server.return_value = make_server(discord_id=200, event_channel_discord_id=None)

        result = await trigger_daily_server_event(200)
        assert result is None

    @patch("src.game.manage_server_events.get_server_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence", new_callable=AsyncMock)
    async def test_returns_none_if_server_not_found(self, mock_existing, mock_server):
        mock_existing.return_value = None
        mock_server.return_value = None

        result = await trigger_daily_server_event(200)
        assert result is None

    @patch("src.game.manage_server_events.to_triggered_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.create_server_event_occurrence", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_random_eligible_server_event_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_active_server_event_occurrence", new_callable=AsyncMock)
    async def test_triggers_new_event(
        self, mock_existing, mock_server, mock_eligible, mock_create, mock_get_occ, mock_to_event
    ):
        mock_existing.return_value = None
        mock_server.return_value = make_server(discord_id=200, event_channel_discord_id=12345)

        event = SimpleNamespace(id=1, name="Town Raffle")
        mock_eligible.return_value = event

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
    def _make_occurrence(
        self, archived=False, resolved_at=None, expired=False, participations=None, event_id=1, max_participants=0
    ):
        occ = MagicMock()
        occ.server_discord_id = 200
        occ.archived = archived
        occ.resolved_at = resolved_at
        occ.expires_at = datetime.now(timezone.utc) + (timedelta(days=-1) if expired else timedelta(days=1))
        occ.server_event_id = event_id
        occ.server_event = MagicMock()
        occ.server_event.name = "Test Event"
        occ.server_event.max_participants = max_participants
        occ.participations = participations or []
        return occ

    def _make_option(self, option_id=1, event_id=1, min_money=0, min_bloodskulls=0, requires_pooch=False, actions=None):
        opt = MagicMock()
        opt.id = option_id
        opt.server_event_id = event_id
        opt.min_money = min_money
        opt.min_bloodskulls = min_bloodskulls
        opt.requires_pooch_selection = requires_pooch
        opt.actions = actions or []
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

    @patch("src.game.manage_server_events.get_server_event_participation", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_already_participated(self, mock_get_occ, mock_get_create, mock_owner_server, mock_existing_part):
        mock_get_occ.return_value = self._make_occurrence()
        mock_owner_server.return_value = MagicMock()
        mock_existing_part.return_value = MagicMock()  # already participated

        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "already participated" in msg.lower()

    @patch("src.game.manage_server_events.get_server_event_option_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_participation", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_event_full(self, mock_get_occ, mock_get_create, mock_owner_server, mock_existing_part, mock_option):
        # Event full: max_participants=1, already has 1 participation
        occ = self._make_occurrence(max_participants=1, participations=[MagicMock()])
        mock_get_occ.return_value = occ
        mock_owner_server.return_value = MagicMock()
        mock_existing_part.return_value = None  # not yet participated
        mock_option.return_value = self._make_option()

        with patch("src.game.manage_server_events.get_owner_by_discord_id", new_callable=AsyncMock) as mock_owner:
            mock_owner.return_value = make_owner(discord_id=100)
            ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)

        assert ok is False
        assert "full" in msg.lower()


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
    @patch("src.game.manage_server_events.finalize_server_event_participation", new_callable=AsyncMock)
    @patch("src.game.manage_server_events._execute_event_actions", new_callable=AsyncMock)
    @patch("src.game.manage_server_events._rank_participations", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_resolve_with_no_participants(self, mock_get, mock_rank, mock_exec, mock_finalize, mock_resolve):
        occ = MagicMock()
        occ.id = 1
        occ.archived = False
        occ.resolved_at = None
        occ.server_discord_id = 200
        occ.server_event = MagicMock()
        occ.server_event.name = "Test"
        occ.server_event.outcomes = []
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
# _compute_participation_score
# ---------------------------------------------------------------------------


class TestComputeParticipationScore:
    @patch("src.game.manage_server_events.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_selected_pooch_health_strategy(self, mock_pooch):
        participation = MagicMock()
        participation.context = {"selected_pooch_id": 5}
        mock_pooch.return_value = SimpleNamespace(base_health=75)

        score = await _compute_participation_score(participation, "selected_pooch_health", random.Random(1))
        assert score == 75.0

    @patch("src.game.manage_server_events.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_selected_pooch_health_no_pooch(self, mock_pooch):
        participation = MagicMock()
        participation.context = {"selected_pooch_id": 5}
        mock_pooch.return_value = None

        score = await _compute_participation_score(participation, "selected_pooch_health", random.Random(1))
        assert score == 0.0

    async def test_selected_pooch_health_no_selected(self):
        participation = MagicMock()
        participation.context = {}

        score = await _compute_participation_score(participation, "selected_pooch_health", random.Random(1))
        assert score == 0.0

    async def test_participation_only_returns_zero(self):
        participation = MagicMock()
        participation.context = {}
        score = await _compute_participation_score(participation, "participation_only", random.Random(1))
        assert score == 0.0

    async def test_random_strategy_returns_float(self):
        participation = MagicMock()
        participation.context = {}
        score = await _compute_participation_score(participation, "random_winner", random.Random(42))
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# _rank_participations
# ---------------------------------------------------------------------------


class TestRankParticipations:
    async def test_ranks_by_score_descending(self):
        p1 = MagicMock()
        p1.context = {}
        p2 = MagicMock()
        p2.context = {}
        occurrence = MagicMock()
        occurrence.server_event.resolution_strategy = "random_winner"
        occurrence.participations = [p1, p2]

        ranked = await _rank_participations(occurrence, random.Random(42))
        assert len(ranked) == 2
        # ranks should be 1 and 2
        ranks = [r[2] for r in ranked]
        assert sorted(ranks) == [1, 2]

    async def test_participation_only_sorts_by_time(self):
        from datetime import datetime, timezone

        p1 = MagicMock()
        p1.context = {}
        p1.participated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        p2 = MagicMock()
        p2.context = {}
        p2.participated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        occurrence = MagicMock()
        occurrence.server_event.resolution_strategy = "participation_only"
        occurrence.participations = [p2, p1]

        ranked = await _rank_participations(occurrence, random.Random(42))
        # p1 participated first, should be rank 1
        assert ranked[0][0] is p1
        assert ranked[0][2] == 1
        assert ranked[1][0] is p2
        assert ranked[1][2] == 2


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
    @patch("src.game.manage_server_events.trigger_daily_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_servers", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.resolve_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_active_server_event_occurrences", new_callable=AsyncMock)
    async def test_resolves_then_triggers(self, mock_active, mock_resolve, mock_servers, mock_trigger):
        occ = MagicMock()
        occ.id = 1
        mock_active.return_value = [occ]
        resolution = MagicMock()
        mock_resolve.return_value = resolution

        server = SimpleNamespace(discord_id=200, event_channel_discord_id=12345)
        mock_servers.return_value = [server]

        new_event = SimpleNamespace(name="New")
        mock_trigger.return_value = new_event

        new_events, resolutions = await run_daily_server_event_cycle()

        assert len(resolutions) == 1
        assert 200 in new_events

    @patch("src.game.manage_server_events.trigger_daily_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_servers", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.resolve_server_event", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.list_active_server_event_occurrences", new_callable=AsyncMock)
    async def test_skips_servers_without_event_channel(self, mock_active, mock_resolve, mock_servers, mock_trigger):
        mock_active.return_value = []
        mock_resolve.return_value = None

        server_no_channel = SimpleNamespace(discord_id=300, event_channel_discord_id=None)
        mock_servers.return_value = [server_no_channel]

        new_events, resolutions = await run_daily_server_event_cycle()
        assert len(new_events) == 0
        mock_trigger.assert_not_awaited()


# ---------------------------------------------------------------------------
# participate_in_server_event — success path and additional edge cases
# ---------------------------------------------------------------------------


class TestParticipateSuccess:
    def _make_occurrence(self, participations=None, event_id=1, max_participants=0):
        occ = MagicMock()
        occ.server_discord_id = 200
        occ.archived = False
        occ.resolved_at = None
        occ.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        occ.server_event_id = event_id
        occ.server_event = MagicMock()
        occ.server_event.name = "Test Event"
        occ.server_event.max_participants = max_participants
        occ.participations = participations or []
        return occ

    def _make_option(self, option_id=1, event_id=1, min_money=0, min_bloodskulls=0, requires_pooch=False, actions=None):
        opt = MagicMock()
        opt.id = option_id
        opt.server_event_id = event_id
        opt.min_money = min_money
        opt.min_bloodskulls = min_bloodskulls
        opt.requires_pooch_selection = requires_pooch
        opt.actions = actions or []
        return opt

    async def test_success_path(self):
        from src.game.models.events.owner_events.owner_event_context import (
            OwnerEventContext,
        )
        from src.game.models.events.owner_events.owner_event_result import (
            OwnerEventResult,
        )

        hydrated_part = MagicMock()
        call_count = 0

        async def get_part_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # First call: check existing participation
            return hydrated_part  # Second call: after creation

        with (
            patch(
                "src.game.manage_server_events.get_server_event_occurrence_by_id",
                new=AsyncMock(return_value=self._make_occurrence()),
            ),
            patch("src.game.manage_server_events.get_or_create_owner", new=AsyncMock()),
            patch("src.game.manage_server_events.get_owner_server", new=AsyncMock(return_value=MagicMock())),
            patch(
                "src.game.manage_server_events.get_server_event_participation",
                new=AsyncMock(side_effect=get_part_side_effect),
            ),
            patch(
                "src.game.manage_server_events.get_server_event_option_by_id",
                new=AsyncMock(return_value=self._make_option()),
            ),
            patch(
                "src.game.manage_server_events.get_owner_by_discord_id",
                new=AsyncMock(return_value=make_owner(discord_id=100, dollars=1000, bloodskulls=10)),
            ),
            patch(
                "src.game.manage_server_events._build_owner_event_context",
                new=AsyncMock(return_value=OwnerEventContext(owner_discord_id=100)),
            ),
            patch(
                "src.game.manage_server_events._execute_event_actions", new=AsyncMock(return_value=OwnerEventResult())
            ),
            patch("src.game.manage_server_events.create_server_event_participation", new=AsyncMock()),
            patch(
                "src.game.manage_server_events.to_server_event_participation_summary",
                new=AsyncMock(return_value=MagicMock()),
            ),
        ):
            ok, msg, summary = await participate_in_server_event(1, 200, 100, 1)

        assert ok is True
        assert "joined" in msg.lower()
        assert summary is not None

    @patch("src.game.manage_server_events.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_option_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_participation", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_not_enough_money(
        self,
        mock_get_occ,
        mock_create_owner,
        mock_owner_server,
        mock_existing_part,
        mock_option,
        mock_owner,
    ):
        mock_get_occ.return_value = self._make_occurrence()
        mock_owner_server.return_value = MagicMock()
        mock_existing_part.return_value = None
        mock_option.return_value = self._make_option(min_money=500)
        mock_owner.return_value = make_owner(discord_id=100, dollars=100, bloodskulls=0)

        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "$500" in msg

    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_owner_not_registered(self, mock_get_occ, mock_create_owner, mock_owner_server):
        mock_get_occ.return_value = self._make_occurrence()
        mock_owner_server.return_value = None
        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "registered" in msg.lower()

    @patch("src.game.manage_server_events.get_server_event_option_by_id", new_callable=AsyncMock)
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

    @patch("src.game.manage_server_events.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_option_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_participation", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_owner_server", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_server_events.get_server_event_occurrence_by_id", new_callable=AsyncMock)
    async def test_owner_not_found(
        self,
        mock_get_occ,
        mock_create_owner,
        mock_owner_server,
        mock_existing_part,
        mock_option,
        mock_owner,
    ):
        mock_get_occ.return_value = self._make_occurrence()
        mock_owner_server.return_value = MagicMock()
        mock_existing_part.return_value = None
        mock_option.return_value = self._make_option()
        mock_owner.return_value = None
        ok, msg, _ = await participate_in_server_event(1, 200, 100, 1)
        assert ok is False
        assert "not found" in msg.lower()
