"""Tests for the new Section 7 breeding helpers (chance, mate selection, neuter)."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.breeding import (
    BreedingOutcome,
    breed_with_mate_choice,
    compute_breeding_chance,
    describe_breeding_outcome,
    get_breeding_chance,
    neuter_pooch,
    select_actual_mate,
)
from src.game.constants import NEUTER_COST


class TestComputeBreedingChance:
    def test_average_intelligence_50_percent(self):
        assert compute_breeding_chance(10) == pytest.approx(0.5)

    def test_low_intelligence_clamped(self):
        assert compute_breeding_chance(0) == 0.1
        assert compute_breeding_chance(-50) == 0.1

    def test_high_intelligence_clamped(self):
        assert compute_breeding_chance(100) == 0.95
        assert compute_breeding_chance(20) == 0.95

    def test_scales_linearly(self):
        # 5 / 20 = 0.25
        assert compute_breeding_chance(5) == pytest.approx(0.25)
        # 15 / 20 = 0.75
        assert compute_breeding_chance(15) == pytest.approx(0.75)


def _female(pooch_id: int):
    return SimpleNamespace(id=pooch_id, sex="female")


class TestSelectActualMate:
    async def test_single_female_always_chosen(self):
        male = SimpleNamespace(id=1, intelligence=2)  # very low → low chance
        intended = _female(10)
        # Only one option → guaranteed.
        result = await select_actual_mate(male, intended, [intended], rng=random.Random(0))
        assert result.id == intended.id

    async def test_high_intelligence_picks_intended(self):
        male = SimpleNamespace(id=1, intelligence=20)  # max chance
        intended = _female(10)
        other = _female(11)
        # 95% chance, but use a seed where the first random < 0.95.
        rng = random.Random(0)
        result = await select_actual_mate(male, intended, [intended, other], rng=rng)
        assert result.id == intended.id

    async def test_low_intelligence_can_pick_other(self):
        male = SimpleNamespace(id=1, intelligence=0)  # 10% chance only
        intended = _female(10)
        other = _female(11)
        # Most rolls should fail and pick "other".
        results = []
        for seed in range(20):
            rng = random.Random(seed)
            result = await select_actual_mate(male, intended, [intended, other], rng=rng)
            results.append(result.id)
        assert other.id in results, "Low-intelligence male should sometimes pick other female"


_MOD = "src.game.breeding"


def _owner(dollars=1000):
    return SimpleNamespace(discord_id=100, dollars=dollars)


class TestNeuterPooch:
    async def test_rejects_unknown_pooch(self):
        with (
            patch(f"{_MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=_owner())),
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(return_value=None)),
            patch(f"{_MOD}.give_money_to_owner", new=AsyncMock()) as give,
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert msg == "Pooch not found."
        give.assert_not_awaited()

    async def test_rejects_non_owner_without_charging(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=999)
        with (
            patch(f"{_MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=_owner())),
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch(f"{_MOD}.give_money_to_owner", new=AsyncMock()) as give,
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert msg == "That's not your pooch."
        give.assert_not_awaited()

    async def test_rejects_dead_pooch(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=False, owner_discord_id=100)
        with (
            patch(f"{_MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=_owner())),
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "dead" in msg

    async def test_rejects_already_neutered(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=100)
        with (
            patch(f"{_MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=_owner())),
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch(f"{_MOD}.list_pooch_injuries", new=AsyncMock(return_value=[SimpleNamespace(name="Neutered")])),
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "already neutered" in msg

    async def test_rejects_when_too_poor(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=100)
        with (
            patch(f"{_MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=_owner(dollars=NEUTER_COST - 1))),
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch(f"{_MOD}.list_pooch_injuries", new=AsyncMock(return_value=[])),
            patch(f"{_MOD}.get_injury_by_name", new=AsyncMock(return_value=SimpleNamespace(id=42))),
            patch(f"{_MOD}.give_money_to_owner", new=AsyncMock()) as give,
            patch(f"{_MOD}.add_injury_to_pooch", new=AsyncMock()) as add_inj,
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is False
        assert "Not enough money" in msg
        give.assert_not_awaited()
        add_inj.assert_not_awaited()

    async def test_success_charges_and_applies_injury(self):
        pooch = SimpleNamespace(id=1, name="Fido", alive=True, owner_discord_id=100)
        with (
            patch(f"{_MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=_owner())),
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch(f"{_MOD}.list_pooch_injuries", new=AsyncMock(return_value=[])),
            patch(f"{_MOD}.get_injury_by_name", new=AsyncMock(return_value=SimpleNamespace(id=42))),
            patch(f"{_MOD}.give_money_to_owner", new=AsyncMock()) as give,
            patch(f"{_MOD}.add_injury_to_pooch", new=AsyncMock()) as add_inj,
        ):
            ok, msg = await neuter_pooch(100, 1)
        assert ok is True
        assert f"${NEUTER_COST}" in msg
        give.assert_awaited_once_with(100, -NEUTER_COST)
        add_inj.assert_awaited_once_with(1, 42)


def _pooch(id, name, sex, owner=100, cooldown=0, alive=True, pregnancy_timer=None, intelligence=10):
    return SimpleNamespace(
        id=id,
        name=name,
        sex=sex,
        owner_discord_id=owner,
        breeding_cooldown=cooldown,
        alive=alive,
        pregnancy_timer=pregnancy_timer,
        intelligence=intelligence,
    )


class TestBreedWithMateChoice:
    async def _run(self, pooches, kennel_pooches, first_id, second_id, picked_id=None, owner=100):
        by_id = {p.id: p for p in pooches}
        eligible_seen = {}

        async def fake_select(male, intended, eligible, rng, chance=None):
            eligible_seen["ids"] = [p.id for p in eligible]
            eligible_seen["chance"] = chance
            return by_id[picked_id] if picked_id is not None else intended

        with (
            patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(side_effect=lambda pid: by_id.get(pid))),
            patch(f"{_MOD}.get_pooch_kennel", new=AsyncMock(return_value=SimpleNamespace(id=7))),
            patch(f"{_MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=kennel_pooches)),
            patch(f"{_MOD}.select_actual_mate", new=fake_select),
            patch(f"{_MOD}.get_breeding_chance", new=AsyncMock(return_value=0.3)),
            patch(f"{_MOD}.breed_pooches", new=AsyncMock(return_value=([50], []))) as breed,
        ):
            outcome = await breed_with_mate_choice(owner, first_id, second_id)
        self.seen_chance = eligible_seen.get("chance")
        return outcome, eligible_seen.get("ids"), breed

    async def test_female_first_still_picks_male_and_only_ready_females(self):
        male = _pooch(1, "Rex", "male")
        chosen = _pooch(2, "Bella", "female")
        other_ready = _pooch(3, "Daisy", "female")
        on_cooldown = _pooch(4, "Molly", "female", cooldown=3)
        pregnant = _pooch(5, "Lucy", "female", pregnancy_timer=10)
        other_male = _pooch(6, "Max", "male")
        kennel = [male, chosen, other_ready, on_cooldown, pregnant, other_male]
        outcome, eligible, breed = await self._run(kennel, kennel, first_id=2, second_id=1)

        assert outcome.male is male
        assert eligible == [2, 3]
        assert self.seen_chance == 0.3
        assert breed.await_args.args[:2] == (1, 2)
        assert outcome.distracted is False

    async def test_distracted_male_breeds_with_other_female(self):
        male = _pooch(1, "Rex", "male")
        chosen = _pooch(2, "Bella", "female")
        other = _pooch(3, "Daisy", "female")
        outcome, _, breed = await self._run([male, chosen, other], [male, chosen, other], 1, 2, picked_id=3)

        assert outcome.distracted is True
        assert outcome.female is other
        assert breed.await_args.args[:2] == (1, 3)

    async def test_rejects_someone_elses_pooch(self):
        male = _pooch(1, "Rex", "male")
        theirs = _pooch(2, "Bella", "female", owner=999)
        with pytest.raises(ValueError, match="That's not your pooch."):
            await self._run([male, theirs], [], 1, 2)

    async def test_rejects_same_sex(self):
        with pytest.raises(ValueError, match="different sexes"):
            await self._run([_pooch(1, "Rex", "male"), _pooch(2, "Max", "male")], [], 1, 2)


class TestDescribeBreedingOutcome:
    def _outcome(self, puppies=1, disease_events=(), distracted=False):
        male = SimpleNamespace(id=1, name="Rex")
        intended = SimpleNamespace(id=2, name="Bella")
        female = SimpleNamespace(id=3, name="Daisy") if distracted else intended
        return BreedingOutcome(list(range(puppies)), list(disease_events), male, female, intended)

    def test_single_puppy(self):
        message, lines = describe_breeding_outcome(self._outcome())
        assert message == "**Breeding successful.** Rex and Bella are expecting **1** puppy."
        assert lines == []

    def test_twins_and_triplets(self):
        assert "**Twins!**" in describe_breeding_outcome(self._outcome(puppies=2))[0]
        assert "**Triplets!**" in describe_breeding_outcome(self._outcome(puppies=3))[0]

    def test_distracted_prefix_names_the_actual_mate(self):
        message, _ = describe_breeding_outcome(self._outcome(distracted=True))
        assert message.startswith("**Rex got distracted** and ended up mating with **Daisy** instead!")
        assert "Rex and Daisy are expecting" in message

    def test_disease_lines(self):
        events = [(1, "Kennel Cough", "spread"), (99, "a cough", "spread"), (50, "Parvovirus", "inherited")]
        _, lines = describe_breeding_outcome(self._outcome(disease_events=events))
        assert lines == [
            "Rex was exposed to Kennel Cough.",
            "A puppy was exposed to a cough.",
            "A puppy inherited Parvovirus.",
        ]


class TestGetBreedingChance:
    async def test_uses_effective_intelligence(self):
        with patch(f"{_MOD}.get_effective_stat", new=AsyncMock(return_value=16)) as stat:
            assert await get_breeding_chance(5) == pytest.approx(0.8)
        stat.assert_awaited_once_with(5, "intelligence")

    async def test_missing_pooch_counts_as_average(self):
        with patch(f"{_MOD}.get_effective_stat", new=AsyncMock(return_value=None)):
            assert await get_breeding_chance(5) == pytest.approx(0.5)

    async def test_select_actual_mate_uses_given_chance(self):
        male, intended, other = SimpleNamespace(id=1, intelligence=20), SimpleNamespace(id=2), SimpleNamespace(id=3)
        rng = random.Random(0)
        picked = await select_actual_mate(male, intended, [intended, other], rng=rng, chance=0.0)
        assert picked is other


class TestImmortalsCannotBreed:
    async def test_breed_pooches_rejects_an_immortal_parent(self):
        from src.game.breeding import breed_pooches

        father = SimpleNamespace(id=1, name="Eternal", sex="male", breeding_cooldown=0, immortal=True)
        mother = SimpleNamespace(id=2, name="Bella", sex="female", breeding_cooldown=0, immortal=False)
        with patch(f"{_MOD}.get_pooch_by_id", new=AsyncMock(side_effect=lambda pid: {1: father, 2: mother}[pid])):
            with pytest.raises(ValueError, match="Eternal is immortal"):
                await breed_pooches(1, 2)
