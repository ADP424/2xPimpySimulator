"""Tests for src/game/breeding.py — name combining, breed_pooches, and incest calculation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game import breed_pooches, calculate_incest_level, combine_puppy_name
from src.game.exceptions import PoochNotFound
from tests.conftest import make_mutation, make_pooch

# ---------------------------------------------------------------------------
# combine_puppy_name
# ---------------------------------------------------------------------------


class TestCombinePuppyName:
    def test_even_length_names(self):
        # "Fido" -> left = "Fi", "Luna" -> right = "na"
        assert combine_puppy_name("Fido", "Luna") == "Fina"

    def test_odd_length_names(self):
        # "Rex" -> left = "R" (3//2=1), "Molly" -> right = "lly" (5//2=2, slice from 2)
        assert combine_puppy_name("Rex", "Molly") == "Rlly"

    def test_single_char_names(self):
        # "A" -> left = "A" (max(0,1)=1), "B" -> right = "B" (1//2=0, slice from 0)
        assert combine_puppy_name("A", "B") == "AB"

    def test_two_char_names(self):
        # "Ab" -> left = "A" (2//2=1), "Cd" -> right = "d" (2//2=1, slice from 1)
        assert combine_puppy_name("Ab", "Cd") == "Ad"

    def test_long_names(self):
        # "Alexander" -> left = "Alex" (9//2=4), "Elizabeth" -> right = "abeth" (9//2=4, slice from 4)
        assert combine_puppy_name("Alexander", "Elizabeth") == "Alexabeth"

    def test_names_with_spaces(self):
        result = combine_puppy_name("Sir Barks", "Lady Woof")
        # "Sir Barks" -> left = "Sir " (9//2=4), "Lady Woof" -> right = " Woof" (9//2=4, slice from 4)
        assert result == "Sir  Woof"

    def test_asymmetric_lengths(self):
        # "Bo" -> left = "B" (2//2=1), "Clementine" -> right = "ntine" (10//2=5, slice from 5)
        assert combine_puppy_name("Bo", "Clementine") == "Bntine"


# ---------------------------------------------------------------------------
# breed_pooches
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_pregnancy_timer():
    """Auto-mock the pregnancy_timer setter so tests don't hit the real DB."""
    with patch("src.game.breeding.set_pooch_pregnancy_timer", new=AsyncMock()):
        yield


class TestBreedPooches:
    """Tests for the breed_pooches async function."""

    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_raises_pooch_not_found_for_first(self, mock_get):
        mock_get.return_value = None
        with pytest.raises(PoochNotFound):
            await breed_pooches(1, 2, rng_seed=42)

    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_raises_pooch_not_found_for_second(self, mock_get):
        father = make_pooch(pooch_id=1, sex="male")
        mock_get.side_effect = lambda pid: father if pid == 1 else None
        with pytest.raises(PoochNotFound):
            await breed_pooches(1, 2, rng_seed=42)

    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_raises_if_same_sex(self, mock_get):
        p1 = make_pooch(pooch_id=1, sex="male")
        p2 = make_pooch(pooch_id=2, sex="male")
        mock_get.side_effect = lambda pid: p1 if pid == 1 else p2
        with pytest.raises(ValueError, match="different sexes"):
            await breed_pooches(1, 2, rng_seed=42)

    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_raises_if_on_cooldown(self, mock_get):
        p1 = make_pooch(pooch_id=1, sex="male", breeding_cooldown=5)
        p2 = make_pooch(pooch_id=2, sex="female", breeding_cooldown=0)
        mock_get.side_effect = lambda pid: p1 if pid == 1 else p2
        with pytest.raises(ValueError, match="breeding cooldown"):
            await breed_pooches(1, 2, rng_seed=42)

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_father_mother_assignment_when_first_is_female(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """When the first pooch is female, it becomes the mother."""
        female = make_pooch(pooch_id=1, sex="female", name="Mama")
        male = make_pooch(pooch_id=2, sex="male", name="Papa")
        mock_get.side_effect = lambda pid: female if pid == 1 else male

        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]  # breed_id 10, weight 1
        mock_mutations.return_value = []

        puppy = make_pooch(pooch_id=99, name="Paama")
        mock_create.return_value = puppy

        # Seed 42 produces a singleton (roll >= 0.25)
        result = await breed_pooches(1, 2, rng_seed=42)

        # Father should be male (id=2), mother should be female (id=1)
        mock_set_virgin.assert_any_call(2, False)  # father
        mock_set_virgin.assert_any_call(1, False)  # mother
        mock_parentage.assert_called_with(99, father_id=2, mother_id=1)
        assert 99 in result

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_singleton_litter(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """When RNG roll >= TWINS_CHANCE (0.25), litter size should be 1."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]
        mock_mutations.return_value = []

        puppy = make_pooch(pooch_id=99)
        mock_create.return_value = puppy

        # Seed 42: rng.random() = 0.6394..., which is >= 0.25 => singleton
        result = await breed_pooches(1, 2, rng_seed=42)
        assert len(result) == 1

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_twins_litter(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """When TRIPLETS_CHANCE <= roll < TWINS_CHANCE, litter size = 2."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]
        mock_mutations.return_value = []

        counter = [90]

        def make_pup(*args, **kwargs):
            pid = counter[0]
            counter[0] += 1
            return make_pooch(pooch_id=pid)

        mock_create.side_effect = make_pup

        # Seed 1: rng.random() = 0.1344..., which is 0.05 <= roll < 0.25 => twins
        result = await breed_pooches(1, 2, rng_seed=1)
        assert len(result) == 2

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_breed_inheritance_50_50(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """Each parent's breeds are normalized and contribute 50% each."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        mock_incest.return_value = 0.0
        # Father is 100% breed A (id=10, weight 2)
        # Mother is 100% breed B (id=20, weight 4)
        mock_breeds.side_effect = lambda pid: [(10, 2)] if pid == 1 else [(20, 4)]
        mock_mutations.return_value = []

        puppy = make_pooch(pooch_id=99)
        mock_create.return_value = puppy

        # Seed 42 produces a singleton (roll >= 0.25)
        await breed_pooches(1, 2, rng_seed=42)

        # Check the add_pooch_breeds call (one puppy = one call)
        mock_add_breeds.assert_called_once()
        call_args = mock_add_breeds.call_args
        puppy_id = call_args[0][0]
        breed_weights = call_args[0][1]
        assert puppy_id == 99
        # Both breeds should be present with equal weight (normalized 50/50)
        assert 10 in breed_weights
        assert 20 in breed_weights
        assert abs(breed_weights[10] - breed_weights[20]) <= 1

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_mutation_inheritance_by_heritability(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """A mutation with heritability=1.0 should always be inherited."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]

        always_inherited = make_mutation(mutation_id=5, heritability=1.0)
        mock_mutations.side_effect = lambda pid: [always_inherited] if pid == 1 else []

        puppy = make_pooch(pooch_id=99)
        mock_create.return_value = puppy

        await breed_pooches(1, 2, rng_seed=42)

        # The mutation should have been added to the puppy
        add_mut_calls = [c for c in mock_add_mut.call_args_list if c.kwargs.get("mutation_id") == 5]
        assert len(add_mut_calls) >= 1

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_double_heritability_when_both_parents_have_mutation(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """When both parents have a mutation, heritability is doubled (capped at 1.0)."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]

        # heritability=0.6 -> doubled = 1.0 (capped), so always inherited
        shared_mut = make_mutation(mutation_id=7, heritability=0.6)
        mock_mutations.return_value = [shared_mut]

        puppy = make_pooch(pooch_id=99)
        mock_create.return_value = puppy

        await breed_pooches(1, 2, rng_seed=42)

        add_mut_calls = [c for c in mock_add_mut.call_args_list if c.kwargs.get("mutation_id") == 7]
        assert len(add_mut_calls) >= 1

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_incest_triggers_random_mutations(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """When incest_level > 0, random mutations can be added (NUM_INCEST_MUTATION_ROLLS=3 attempts)."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        mock_incest.return_value = 1.0  # 100% incest => all rolls succeed
        mock_breeds.return_value = [(10, 1)]
        mock_mutations.return_value = []

        puppy = make_pooch(pooch_id=99)
        mock_create.return_value = puppy

        await breed_pooches(1, 2, rng_seed=42)

        # With incest_level=1.0, all 3 incest mutation rolls should succeed
        # These calls are the ones with rng= kwarg and no mutation_id
        random_mut_calls = [
            c for c in mock_add_mut.call_args_list if "mutation_id" not in c.kwargs and c.kwargs.get("rng") is not None
        ]
        assert len(random_mut_calls) == 3

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch("src.game.breeding.handle_breeding_diseases", new_callable=AsyncMock, return_value=[])
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_skip_validation_bypasses_all_checks(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        """skip_validation=True should allow breeding even with same sex, cooldown, etc."""
        p1 = make_pooch(pooch_id=1, sex="male", name="Dad", breeding_cooldown=99)
        p2 = make_pooch(pooch_id=2, sex="male", name="Dad2", breeding_cooldown=99)
        mock_get.side_effect = lambda pid: p1 if pid == 1 else p2

        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]
        mock_mutations.return_value = []

        puppy = make_pooch(pooch_id=99)
        mock_create.return_value = puppy

        result = await breed_pooches(1, 2, rng_seed=42, skip_validation=True)
        assert len(result) >= 1

    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_skip_validation_still_refuses_a_pregnant_mother(self, mock_get, mock_reset_cd):
        """Event breeding (skip_validation=True) must not start a second litter in a pregnant female."""
        father = make_pooch(pooch_id=1, sex="male", name="Dad")
        mother = make_pooch(pooch_id=2, sex="female", name="Mom", pregnancy_timer=12)
        mock_get.side_effect = lambda pid: father if pid == 1 else mother

        with pytest.raises(ValueError, match="already pregnant"):
            await breed_pooches(1, 2, rng_seed=42, skip_validation=True)
        mock_reset_cd.assert_not_awaited()


# ---------------------------------------------------------------------------
# calculate_incest_level
# ---------------------------------------------------------------------------


class TestCalculateIncestLevel:
    async def test_same_pooch_returns_one(self):
        result = await calculate_incest_level(1, 1)
        assert result == 1.0

    @patch("src.game.breeding.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_parents", new_callable=AsyncMock)
    async def test_unrelated_pooches_return_zero(self, mock_parents, mock_children, mock_siblings):
        """Two pooches with no family connection should return 0.0."""
        mock_parents.return_value = (None, None)
        mock_children.return_value = []
        mock_siblings.return_value = []

        result = await calculate_incest_level(1, 2)
        assert result == 0.0

    @patch("src.game.breeding.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_parents", new_callable=AsyncMock)
    async def test_parent_child_returns_half(self, mock_parents, mock_children, mock_siblings):
        """Parent-child relationship = 1 jump = 0.5."""

        # Pooch 1 has child 2
        def parents_side_effect(pid):
            if pid == 1:
                return (None, None)
            return (None, None)

        mock_parents.side_effect = parents_side_effect
        mock_children.side_effect = lambda pid: [make_pooch(pooch_id=2)] if pid == 1 else []
        mock_siblings.return_value = []

        result = await calculate_incest_level(1, 2)
        assert result == 0.5

    @patch("src.game.breeding.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_parents", new_callable=AsyncMock)
    async def test_siblings_return_half(self, mock_parents, mock_children, mock_siblings):
        """Siblings (via sibling list) = 1 jump = 0.5."""
        mock_parents.return_value = (None, None)
        mock_children.return_value = []
        mock_siblings.side_effect = lambda pid: [make_pooch(pooch_id=2)] if pid == 1 else [make_pooch(pooch_id=1)]

        result = await calculate_incest_level(1, 2)
        assert result == 0.5

    @patch("src.game.breeding.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_parents", new_callable=AsyncMock)
    async def test_grandparent_returns_quarter(self, mock_parents, mock_children, mock_siblings):
        """Grandparent-grandchild = 2 jumps = 0.25."""
        # Pooch 1 -> child 3 -> child 2
        mock_parents.return_value = (None, None)
        mock_children.side_effect = lambda pid: (
            [make_pooch(pooch_id=3)] if pid == 1 else ([make_pooch(pooch_id=2)] if pid == 3 else [])
        )
        mock_siblings.return_value = []

        result = await calculate_incest_level(1, 2)
        assert result == 0.25

    @patch("src.game.breeding.list_pooch_siblings", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_children", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_parents", new_callable=AsyncMock)
    async def test_max_depth_limits_search(self, mock_parents, mock_children, mock_siblings):
        """If the relation is deeper than max_depth, returns 0.0."""
        mock_parents.return_value = (None, None)
        # A chain: 1 -> 10 -> 11 -> 12 -> 2, but max_depth=2 stops before reaching 2
        mock_children.side_effect = lambda pid: {
            1: [make_pooch(pooch_id=10)],
            10: [make_pooch(pooch_id=11)],
            11: [make_pooch(pooch_id=12)],
            12: [make_pooch(pooch_id=2)],
        }.get(pid, [])
        mock_siblings.return_value = []

        result = await calculate_incest_level(1, 2, max_depth=2)
        assert result == 0.0

    @patch("src.database.get_current_season", new_callable=AsyncMock, return_value="spring")
    @patch(
        "src.game.breeding.handle_breeding_diseases",
        new_callable=AsyncMock,
        return_value=[(2, "a mysterious illness", "spread")],
    )
    @patch("src.game.breeding.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.add_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch_pregnancy", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_parentage", new_callable=AsyncMock)
    @patch("src.game.breeding.create_pooch", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.breeding.list_pooch_breed_weights", new_callable=AsyncMock)
    @patch("src.game.breeding.calculate_incest_level", new_callable=AsyncMock)
    @patch("src.game.breeding.set_pooch_virgin", new_callable=AsyncMock)
    @patch("src.game.breeding.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.breeding.get_pooch_by_id", new_callable=AsyncMock)
    async def test_breed_pooches_can_return_disease_events(
        self,
        mock_get,
        mock_reset_cd,
        mock_set_virgin,
        mock_incest,
        mock_breeds,
        mock_mutations,
        mock_create,
        mock_parentage,
        mock_pregnancy,
        mock_add_breeds,
        mock_add_mut,
        mock_handle_diseases,
        mock_get_season,
    ):
        father = make_pooch(pooch_id=1, sex="male", name="Papa")
        mother = make_pooch(pooch_id=2, sex="female", name="Mama")
        mock_get.side_effect = lambda pid: father if pid == 1 else mother
        mock_incest.return_value = 0.0
        mock_breeds.return_value = [(10, 1)]
        mock_mutations.return_value = []
        mock_create.return_value = SimpleNamespace(id=99)

        result = await breed_pooches(1, 2, rng_seed=42, return_disease_events=True)

        assert result == ([99], [(2, "a mysterious illness", "spread")])
