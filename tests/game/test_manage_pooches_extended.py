"""Additional tests for src/game/manage_pooches.py — vet functions, rating helpers, injury persistence."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.manage_pooches import (
    MEDICAL_EXAM_COST,
    _pooch_status,
    _rate_stat,
    diagnose_injuries,
    diagnose_mutations,
    get_diagnose_injuries_cost,
    get_diagnose_mutations_cost,
    get_pooch_family,
    get_public_injury_label,
    get_treatment_cost,
    is_injury_treated_today,
    list_snapshots_for_pooch,
    mark_pooch_vet_checked,
    medical_exam,
    run_hourly_injury_persistence_check,
    treat_injury,
)
from tests.conftest import make_owner, make_pooch

# ---------------------------------------------------------------------------
# _pooch_status
# ---------------------------------------------------------------------------


class TestPoochStatus:
    def test_dead(self):
        assert _pooch_status(alive=False, age=5, health=10) == "dead"

    def test_dead_takes_priority_over_old(self):
        assert _pooch_status(alive=False, age=15, health=10) == "dead"

    def test_dead_takes_priority_over_sick(self):
        assert _pooch_status(alive=False, age=2, health=1) == "dead"

    def test_old_exactly_12(self):
        assert _pooch_status(alive=True, age=12, health=10) == "old"

    def test_old_above_12(self):
        assert _pooch_status(alive=True, age=20, health=10) == "old"

    def test_old_beats_sick(self):
        assert _pooch_status(alive=True, age=15, health=3) == "old"

    def test_sick_at_3(self):
        assert _pooch_status(alive=True, age=2, health=3) == "sick"

    def test_sick_at_1(self):
        assert _pooch_status(alive=True, age=2, health=1) == "sick"

    def test_healthy(self):
        assert _pooch_status(alive=True, age=2, health=10) == "healthy"

    def test_healthy_just_above_sick_threshold(self):
        assert _pooch_status(alive=True, age=2, health=4) == "healthy"

    def test_healthy_just_below_old_threshold(self):
        assert _pooch_status(alive=True, age=11, health=10) == "healthy"


# ---------------------------------------------------------------------------
# _rate_stat
# ---------------------------------------------------------------------------


class TestRateStat:
    def test_significantly_below_average(self):
        assert _rate_stat(1) == "Significantly Below Average"
        assert _rate_stat(4) == "Significantly Below Average"

    def test_below_average(self):
        assert _rate_stat(5) == "Below Average"
        assert _rate_stat(7) == "Below Average"

    def test_slightly_below_average(self):
        assert _rate_stat(8) == "Slightly Below Average"
        assert _rate_stat(9) == "Slightly Below Average"

    def test_average(self):
        assert _rate_stat(10) == "Average"

    def test_slightly_above_average(self):
        assert _rate_stat(11) == "Slightly Above Average"
        assert _rate_stat(12) == "Slightly Above Average"

    def test_above_average(self):
        assert _rate_stat(13) == "Above Average"
        assert _rate_stat(15) == "Above Average"

    def test_significantly_above_average(self):
        assert _rate_stat(16) == "Significantly Above Average"
        assert _rate_stat(100) == "Significantly Above Average"


# ---------------------------------------------------------------------------
# get_treatment_cost
# ---------------------------------------------------------------------------


class TestGetTreatmentCost:
    def test_trivial(self):
        # level 1: 10 + 5*1 = 15
        assert get_treatment_cost("trivial") == 15

    def test_minor(self):
        # level 2: 10 + 5*2 = 20
        assert get_treatment_cost("minor") == 20

    def test_moderate(self):
        # level 3: 10 + 5*3 = 25
        assert get_treatment_cost("moderate") == 25

    def test_major(self):
        # level 4: 10 + 5*4 = 30
        assert get_treatment_cost("major") == 30

    def test_critical(self):
        # level 5: 10 + 5*5 = 35
        assert get_treatment_cost("critical") == 35

    def test_remarkable(self):
        # level 6: 10 + 5*6 = 40
        assert get_treatment_cost("remarkable") == 40

    def test_catastrophic(self):
        # level 7: 10 + 5*7 = 45
        assert get_treatment_cost("catastrophic") == 45

    def test_unknown_defaults_to_level_2(self):
        # unknown maps to default level 2: 10 + 5*2 = 20
        assert get_treatment_cost("nonexistent") == 20

    def test_case_insensitive(self):
        assert get_treatment_cost("TRIVIAL") == get_treatment_cost("trivial")
        assert get_treatment_cost("Major") == get_treatment_cost("major")


# ---------------------------------------------------------------------------
# get_diagnose_injuries_cost / get_diagnose_mutations_cost
# ---------------------------------------------------------------------------


class TestDiagnoseCosts:
    def test_injuries_cost_is_int(self):
        cost = get_diagnose_injuries_cost()
        assert isinstance(cost, int)
        assert cost > 0

    def test_mutations_cost_is_int(self):
        cost = get_diagnose_mutations_cost()
        assert isinstance(cost, int)
        assert cost > 0

    def test_injuries_cost_matches_constant(self):
        from src.game.constants import VET_DIAGNOSE_INJURIES_COST

        assert get_diagnose_injuries_cost() == VET_DIAGNOSE_INJURIES_COST

    def test_mutations_cost_matches_constant(self):
        from src.game.constants import VET_DIAGNOSE_MUTATIONS_COST

        assert get_diagnose_mutations_cost() == VET_DIAGNOSE_MUTATIONS_COST


# ---------------------------------------------------------------------------
# run_hourly_injury_persistence_check
# ---------------------------------------------------------------------------


class TestRunHourlyInjuryPersistenceCheck:
    @patch("src.game.manage_pooches.tick_hourly_injury_persistence", new_callable=AsyncMock)
    async def test_returns_count(self, mock_tick):
        mock_tick.return_value = 3
        result = await run_hourly_injury_persistence_check(rng_seed=42)
        assert result == 3

    @patch("src.game.manage_pooches.tick_hourly_injury_persistence", new_callable=AsyncMock)
    async def test_passes_divisor_and_seed(self, mock_tick):
        mock_tick.return_value = 0
        await run_hourly_injury_persistence_check(rng_seed=7)
        mock_tick.assert_awaited_once_with(constitution_divisor=50, rng_seed=7)

    @patch("src.game.manage_pooches.tick_hourly_injury_persistence", new_callable=AsyncMock)
    async def test_no_seed(self, mock_tick):
        mock_tick.return_value = 2
        result = await run_hourly_injury_persistence_check()
        assert result == 2
        mock_tick.assert_awaited_once_with(constitution_divisor=50, rng_seed=None)


# ---------------------------------------------------------------------------
# mark_pooch_vet_checked
# ---------------------------------------------------------------------------


class TestMarkPoochVetChecked:
    @patch("src.game.manage_pooches.set_pooch_vet_checked", new_callable=AsyncMock)
    async def test_calls_set_vet_checked(self, mock_set):
        await mark_pooch_vet_checked(42)
        mock_set.assert_awaited_once_with(42, checked=True)


# ---------------------------------------------------------------------------
# list_snapshots_for_pooch
# ---------------------------------------------------------------------------


class TestListSnapshotsForPooch:
    @patch("src.game.manage_pooches.db_list_pooch_snapshots", new_callable=AsyncMock)
    async def test_returns_snapshots(self, mock_list):
        mock_list.return_value = [{"id": 1}, {"id": 2}]
        result = await list_snapshots_for_pooch(5)
        assert len(result) == 2
        mock_list.assert_awaited_once_with(5)

    @patch("src.game.manage_pooches.db_list_pooch_snapshots", new_callable=AsyncMock)
    async def test_empty_list(self, mock_list):
        mock_list.return_value = []
        result = await list_snapshots_for_pooch(99)
        assert result == []


# ---------------------------------------------------------------------------
# medical_exam
# ---------------------------------------------------------------------------


class TestMedicalExam:
    def _make_game_pooch(self, **overrides):
        """Build a SimpleNamespace that mimics a game Pooch model."""
        defaults = dict(
            id=1,
            name="Buddy",
            strength=10,
            cuteness=8,
            fluffiness=12,
            intelligence=10,
            dexterity=9,
            fertility=11,
            aggressiveness=7,
            constitution=10,
            size=10,
            owner_discord_id=1,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_not_your_pooch(self, mock_get_owner, mock_give_money):
        mock_get_owner.return_value = make_owner(discord_id=2, dollars=1000)
        pooch = self._make_game_pooch(owner_discord_id=1)

        success, msg, report = await medical_exam(2, pooch)

        assert success is False
        assert msg == "That's not your pooch."
        assert report == {}
        mock_give_money.assert_not_awaited()

    @patch("src.game.manage_pooches.create_pooch_snapshot", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_success(self, mock_get_owner, mock_give_money, mock_snapshot):
        owner = make_owner(discord_id=1, dollars=200)
        mock_get_owner.return_value = owner
        pooch = self._make_game_pooch()

        success, msg, report = await medical_exam(1, pooch)

        assert success is True
        assert msg == ""
        assert "Strength" in report
        assert "Size Class" in report
        mock_give_money.assert_awaited_once_with(1, -MEDICAL_EXAM_COST)
        mock_snapshot.assert_awaited_once()

    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_owner_not_found(self, mock_get_owner):
        mock_get_owner.return_value = None
        pooch = self._make_game_pooch()

        success, msg, report = await medical_exam(999, pooch)

        assert success is False
        assert "Owner not found" in msg
        assert report == {}

    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_insufficient_funds(self, mock_get_owner):
        owner = make_owner(discord_id=1, dollars=MEDICAL_EXAM_COST - 1)
        mock_get_owner.return_value = owner
        pooch = self._make_game_pooch()

        success, msg, report = await medical_exam(1, pooch)

        assert success is False
        assert "Not enough money" in msg
        assert report == {}

    @patch("src.game.manage_pooches.create_pooch_snapshot", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_report_has_all_stats(self, mock_get_owner, mock_give_money, mock_snapshot):
        owner = make_owner(discord_id=1, dollars=1000)
        mock_get_owner.return_value = owner
        pooch = self._make_game_pooch(
            strength=5,
            cuteness=15,
            fluffiness=10,
            intelligence=2,
            dexterity=11,
            fertility=13,
            aggressiveness=9,
            constitution=16,
            size=8,
        )

        _, _, report = await medical_exam(1, pooch)

        expected_keys = {
            "Strength",
            "Cuteness",
            "Fluffiness",
            "Intelligence",
            "Dexterity",
            "Fertility",
            "Aggressiveness",
            "Constitution",
            "Size Class",
        }
        assert set(report.keys()) == expected_keys

    @patch("src.game.manage_pooches.create_pooch_snapshot", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_exact_cost_funds_succeeds(self, mock_get_owner, mock_give_money, mock_snapshot):
        owner = make_owner(discord_id=1, dollars=MEDICAL_EXAM_COST)
        mock_get_owner.return_value = owner
        pooch = self._make_game_pooch()

        success, _, _ = await medical_exam(1, pooch)
        assert success is True


# ---------------------------------------------------------------------------
# treat_injury
# ---------------------------------------------------------------------------


class TestInjuryHelpers:
    def test_visible_injury_shows_real_name(self):
        pi = SimpleNamespace(visible=True, injury=SimpleNamespace(name="Sprain"), displayed_symptom="a limp")
        assert get_public_injury_label(pi) == "Sprain"

    def test_hidden_injury_uses_displayed_symptom(self):
        pi = SimpleNamespace(visible=False, injury=SimpleNamespace(name="Sprain"), displayed_symptom="a limp")
        assert get_public_injury_label(pi) == "a limp"

    def test_hidden_injury_without_symptom_uses_generic_label(self):
        pi = SimpleNamespace(visible=False, injury=SimpleNamespace(name="Sprain"), displayed_symptom=None)
        assert get_public_injury_label(pi) == "a mysterious injury"

    def test_never_treated(self):
        assert is_injury_treated_today(SimpleNamespace(last_treated_at=None)) is False

    def test_treated_today_naive_datetime(self):
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert is_injury_treated_today(SimpleNamespace(last_treated_at=now_naive)) is True

    def test_treated_on_earlier_day(self):
        earlier = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert is_injury_treated_today(SimpleNamespace(last_treated_at=earlier)) is False


class TestTreatInjury:
    def _make_pi(self, severity="minor", persistence=5, last_treated_at=None, owner_discord_id=1):
        return SimpleNamespace(
            injury=SimpleNamespace(severity=severity),
            persistence=persistence,
            last_treated_at=last_treated_at,
            pooch=SimpleNamespace(owner_discord_id=owner_discord_id),
        )

    @patch("src.game.manage_pooches.reduce_pooch_injury_persistence", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.treat_pooch_injury", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_injury_not_found(self, mock_get_pi, mock_get_owner, mock_give, mock_treat, mock_reduce):
        mock_get_pi.return_value = None

        success, msg, cost = await treat_injury(1, 99)
        assert success is False
        assert "not found" in msg.lower()
        assert cost == 0

    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_not_your_pooch(self, mock_get_pi, mock_get_owner, mock_give):
        mock_get_pi.return_value = self._make_pi(owner_discord_id=1)
        mock_get_owner.return_value = make_owner(discord_id=2, dollars=1000)

        success, msg, cost = await treat_injury(2, 1)
        assert success is False
        assert msg == "That's not your pooch."
        assert cost == 0
        mock_give.assert_not_awaited()

    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_owner_not_found(self, mock_get_pi, mock_get_owner):
        mock_get_pi.return_value = self._make_pi()
        mock_get_owner.return_value = None

        success, msg, cost = await treat_injury(1, 1)
        assert success is False
        assert "Owner not found" in msg

    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_insufficient_funds(self, mock_get_pi, mock_get_owner):
        mock_get_pi.return_value = self._make_pi(severity="catastrophic")  # cost = 45
        mock_get_owner.return_value = make_owner(dollars=10)  # less than 45

        success, msg, cost = await treat_injury(1, 1)
        assert success is False
        assert "Not enough money" in msg
        assert cost == 0

    @patch("src.game.manage_pooches.reduce_pooch_injury_persistence", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.treat_pooch_injury", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_success_charges_correct_cost(self, mock_get_pi, mock_get_owner, mock_give, mock_treat, mock_reduce):
        mock_get_pi.return_value = self._make_pi(severity="minor")  # cost = 20
        mock_get_owner.return_value = make_owner(dollars=100)

        success, msg, cost = await treat_injury(1, 1)
        assert success is True
        assert cost == 20
        mock_give.assert_awaited_once_with(1, -20)

    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_already_treated_today(self, mock_get_pi, mock_get_owner):
        mock_get_pi.return_value = self._make_pi(last_treated_at=datetime.now(timezone.utc))
        mock_get_owner.return_value = make_owner(dollars=1000)

        success, msg, cost = await treat_injury(1, 1)
        assert success is False
        assert "already been treated" in msg

    @patch("src.game.manage_pooches.reduce_pooch_injury_persistence", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.treat_pooch_injury", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_injury_instance", new_callable=AsyncMock)
    async def test_no_persistence_skips_reduction(
        self, mock_get_pi, mock_get_owner, mock_give, mock_treat, mock_reduce
    ):
        mock_get_pi.return_value = self._make_pi(persistence=None)
        mock_get_owner.return_value = make_owner(dollars=100)

        success, _, _ = await treat_injury(1, 1)
        assert success is True
        mock_reduce.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_pooch_family
# ---------------------------------------------------------------------------


class TestGetPoochFamily:
    @patch("src.game.manage_pooches.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_parents", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.to_pooch", new_callable=AsyncMock)
    async def test_returns_family_dict(self, mock_to_pooch, mock_parents, mock_children, mock_siblings):
        father = SimpleNamespace(id=10)
        mother = SimpleNamespace(id=11)
        child = SimpleNamespace(id=20)
        sibling = SimpleNamespace(id=30)

        mock_parents.return_value = (father, mother)
        mock_children.return_value = [child]
        mock_siblings.return_value = [sibling]
        mock_to_pooch.side_effect = lambda p: SimpleNamespace(id=p.id)

        result = await get_pooch_family(5)

        assert len(result["parents"]) == 2
        assert len(result["children"]) == 1
        assert len(result["siblings"]) == 1

    @patch("src.game.manage_pooches.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_pooch_parents", new_callable=AsyncMock)
    async def test_no_parents(self, mock_parents, mock_children, mock_siblings):
        mock_parents.return_value = (None, None)
        mock_children.return_value = []
        mock_siblings.return_value = []

        result = await get_pooch_family(5)
        assert result["parents"] == []
        assert result["children"] == []
        assert result["siblings"] == []


# ---------------------------------------------------------------------------
# diagnose_injuries
# ---------------------------------------------------------------------------


class TestDiagnoseInjuries:
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_owner_not_found(self, mock_get_owner):
        mock_get_owner.return_value = None
        success, msg, revealed = await diagnose_injuries(999, 1)
        assert success is False
        assert "Owner not found" in msg

    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_insufficient_funds(self, mock_get_owner, mock_db_get):
        mock_get_owner.return_value = make_owner(dollars=0)
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        success, msg, revealed = await diagnose_injuries(1, 1)
        assert success is False
        assert "Not enough money" in msg

    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_not_your_pooch(self, mock_get_owner, mock_db_get, mock_give):
        mock_get_owner.return_value = make_owner(discord_id=2, dollars=1000)
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        success, msg, revealed = await diagnose_injuries(2, 1)
        assert success is False
        assert msg == "That's not your pooch."
        assert revealed == []
        mock_give.assert_not_awaited()

    @patch("src.game.manage_pooches.create_pooch_snapshot", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.set_pooch_vet_checked", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.list_pooch_injury_instances", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.reveal_pooch_injury", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_success_reveals_injury(
        self,
        mock_get_owner,
        mock_give,
        mock_reveal,
        mock_db_get,
        mock_list_inj,
        mock_vet_check,
        mock_snapshot,
    ):
        mock_get_owner.return_value = make_owner(dollars=100)
        # One invisible injury with reveal_chance=1.0, plus an already-visible one that must be skipped
        inj = SimpleNamespace(id=7, injury=SimpleNamespace(id=7, name="Bite", reveal_chance=1.0), visible=False)
        seen = SimpleNamespace(id=8, injury=SimpleNamespace(id=8, name="Bruise", reveal_chance=1.0), visible=True)
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        mock_list_inj.side_effect = [[inj, seen], [SimpleNamespace(injury_id=7, visible=True)]]

        success, msg, revealed = await diagnose_injuries(1, 1, rng_seed=42)

        assert success is True
        assert revealed == ["Bite"]
        mock_reveal.assert_awaited_once_with(7)

    @patch("src.game.manage_pooches.create_pooch_snapshot", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.set_pooch_vet_checked", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.list_pooch_injury_instances", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.reveal_pooch_injury", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_injury_not_revealed_when_chance_zero(
        self,
        mock_get_owner,
        mock_give,
        mock_reveal,
        mock_db_get,
        mock_list_inj,
        mock_vet_check,
        mock_snapshot,
    ):
        mock_get_owner.return_value = make_owner(dollars=100)
        inj = SimpleNamespace(id=7, injury=SimpleNamespace(id=7, name="Scratch", reveal_chance=0.0), visible=False)
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        mock_list_inj.side_effect = [[inj], []]

        success, _, revealed = await diagnose_injuries(1, 1, rng_seed=0)

        assert success is True
        assert revealed == []
        mock_reveal.assert_not_awaited()


# ---------------------------------------------------------------------------
# diagnose_mutations
# ---------------------------------------------------------------------------


class TestDiagnoseMutations:
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_owner_not_found(self, mock_get_owner):
        mock_get_owner.return_value = None
        success, msg, revealed = await diagnose_mutations(999, 1)
        assert success is False
        assert "Owner not found" in msg

    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_insufficient_funds(self, mock_get_owner, mock_db_get):
        mock_get_owner.return_value = make_owner(dollars=0)
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        success, msg, revealed = await diagnose_mutations(1, 1)
        assert success is False
        assert "Not enough money" in msg

    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_not_your_pooch(self, mock_get_owner, mock_db_get, mock_give):
        mock_get_owner.return_value = make_owner(discord_id=2, dollars=1000)
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        success, msg, revealed = await diagnose_mutations(2, 1)
        assert success is False
        assert msg == "That's not your pooch."
        assert revealed == []
        mock_give.assert_not_awaited()

    @patch("src.game.manage_pooches.create_pooch_snapshot", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.set_pooch_vet_checked", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.list_pooch_mutation_instances", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.reveal_pooch_mutation", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_pooches.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_success_reveals_mutation(
        self,
        mock_get_owner,
        mock_give,
        mock_reveal,
        mock_db_get,
        mock_list_mut,
        mock_vet_check,
        mock_snapshot,
    ):
        mock_get_owner.return_value = make_owner(dollars=200)
        pm = SimpleNamespace(
            pooch_id=1, mutation_id=3, mutation=SimpleNamespace(name="Albinism", reveal_chance=1.0), visible=False
        )
        mock_db_get.return_value = SimpleNamespace(name="Buddy", owner_discord_id=1)
        mock_list_mut.side_effect = [[pm], [SimpleNamespace(mutation_id=3, visible=True)]]

        success, _, revealed = await diagnose_mutations(1, 1, rng_seed=42)

        assert success is True
        assert "Albinism" in revealed
        mock_reveal.assert_awaited_once_with(1, 3)
