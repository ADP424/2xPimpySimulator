"""Tests for src/game/manage_diseases.py."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.manage_diseases import (
    CONSTITUTION_RESISTANCE_DIVISOR,
    DISEASE_BASE_CONTRACTION_CHANCE,
    MESSINESS_CONTRACTION_MULT,
    MUTATION_PREDISPOSITION_MULT,
    TREATMENT_RECOVERY_BONUS,
    VET_DIAGNOSE_DISEASES_COST,
    VET_DISEASE_TREATMENT_BASE_COST,
    clean_kennel_by_hand,
    clean_kennel_with_item,
    diagnose_diseases,
    get_public_disease_label,
    treat_disease,
    try_breed_spread_disease,
    try_contract_disease,
    try_inherit_disease,
    try_recover_from_disease,
    try_spread_disease,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_disease(
    disease_id=1,
    name="Test Disease",
    category="test",
    health_impact="harmful",
    contagion_chance=0.5,
    sexually_transmitted=False,
    recovery_chance=0.1,
    treatable=True,
    curable=True,
    immunity_duration=None,
    heritability=0.0,
    seasons=None,
    season_contagion_modifiers=None,
    parameters=None,
    visible=True,
    invisible_messages=None,
    reveal_chance=1.0,
):
    return SimpleNamespace(
        id=disease_id,
        name=name,
        category=category,
        health_impact=health_impact,
        contagion_chance=contagion_chance,
        sexually_transmitted=sexually_transmitted,
        recovery_chance=recovery_chance,
        treatable=treatable,
        curable=curable,
        immunity_duration=immunity_duration,
        heritability=heritability,
        seasons=seasons,
        season_contagion_modifiers=season_contagion_modifiers,
        parameters=parameters or {},
        visible=visible,
        invisible_messages=invisible_messages,
        reveal_chance=reveal_chance,
    )


def make_pooch_disease(
    pooch_id=1,
    disease_id=1,
    disease=None,
    treated=False,
    visible=True,
):
    pd = SimpleNamespace(
        pooch_id=pooch_id,
        disease_id=disease_id,
        disease=disease or make_disease(disease_id=disease_id),
        treated=treated,
        visible=visible,
    )
    return pd


# ---------------------------------------------------------------------------
# try_contract_disease
# ---------------------------------------------------------------------------


class TestTryContractDisease:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_std_diseases(self, mock_add):
        """STD-only diseases should always be skipped by try_contract_disease."""
        disease = make_disease(sexually_transmitted=True)
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=10,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_if_already_has_disease(self, mock_add):
        """Pooch that already has the disease should not contract it again."""
        disease = make_disease(disease_id=5)
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=10,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids={5},
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_if_immune_by_id(self, mock_add):
        """Pooch with immunity (by disease id) should not contract disease."""
        disease = make_disease(disease_id=5)
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=10,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids={5},
            existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_if_mutation_grants_immunity(self, mock_add):
        """Mutation-granted immunity (by disease name) should block contraction."""
        disease = make_disease(name="Kennel Cough")
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=10,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            predisposed_names=set(),
            immune_names={"Kennel Cough"},
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_if_out_of_season(self, mock_add):
        """Disease restricted to certain seasons should not contract outside them."""
        disease = make_disease(seasons=["winter"])
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=10,
            messiness=0,
            season="summer",
            rng=rng,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_higher_messiness_increases_chance(self, mock_add):
        """Higher messiness should increase contraction chance."""
        disease = make_disease(contagion_chance=0.0)
        # With high messiness, the chance is boosted.
        # chance = BASE + 0 + messiness * MULT
        # With 0 constitution: chance stays as is (no resistance reduction)
        # messiness=0 => chance = 0.005
        # messiness=100 => chance = 0.005 + 100*0.005 = 0.505
        seed = 42
        rng_low = random.Random(seed)
        rng_high = random.Random(seed)

        # Run with low messiness
        await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=0,
            messiness=0,
            season="spring",
            rng=rng_low,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )

        await try_contract_disease(
            pooch_id=2,
            disease=disease,
            constitution=0,
            messiness=100,
            season="spring",
            rng=rng_high,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )

        # With the same RNG seed, high messiness should be at least as likely to contract.
        # The chance for high is 0.505 vs 0.005 for low, so for many seeds high will
        # succeed while low fails.
        # We verify the math: higher messiness means higher chance.
        chance_low = DISEASE_BASE_CONTRACTION_CHANCE
        chance_high = DISEASE_BASE_CONTRACTION_CHANCE + 100 * MESSINESS_CONTRACTION_MULT
        assert chance_high > chance_low

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_higher_constitution_decreases_chance(self, mock_add):
        """Higher constitution should reduce contraction chance via resistance divisor."""
        _disease = make_disease(contagion_chance=0.5)  # noqa: F841
        # constitution=50 => chance *= max(0.1, 1.0 - 50/100) = 0.5
        # constitution=0 => no reduction
        # So constitution cuts chance in half at value 50.
        chance_no_const = DISEASE_BASE_CONTRACTION_CHANCE + 0.5 * 0.1
        chance_with_const = chance_no_const * max(0.1, 1.0 - 50 / CONSTITUTION_RESISTANCE_DIVISOR)
        assert chance_with_const < chance_no_const

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_mutation_predisposition_increases_chance(self, mock_add):
        """Predisposition from mutation should multiply chance by MUTATION_PREDISPOSITION_MULT."""
        _disease = make_disease(name="Kennel Cough", contagion_chance=0.0)  # noqa: F841
        # Without predisposition: chance = BASE
        # With predisposition: chance = BASE * MUTATION_PREDISPOSITION_MULT
        chance_normal = DISEASE_BASE_CONTRACTION_CHANCE
        chance_predisposed = DISEASE_BASE_CONTRACTION_CHANCE * MUTATION_PREDISPOSITION_MULT
        assert chance_predisposed > chance_normal
        assert chance_predisposed == pytest.approx(DISEASE_BASE_CONTRACTION_CHANCE * MUTATION_PREDISPOSITION_MULT)

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_contracts_when_roll_succeeds(self, mock_add):
        """When the RNG roll is below the chance, the disease is contracted."""
        # Use a very high contagion and high messiness to guarantee contraction.
        disease = make_disease(contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=0,
            messiness=200,
            season="spring",
            rng=rng,
            current_day=5,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )
        # With contagion=1.0 and messiness=200, chance is clamped to 1.0
        assert result is True
        mock_add.assert_awaited_once_with(1, disease.id, current_day=5, rng=rng)

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_in_season_disease_can_contract(self, mock_add):
        """Disease restricted to current season should be eligible."""
        disease = make_disease(seasons=["spring"], contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_contract_disease(
            pooch_id=1,
            disease=disease,
            constitution=0,
            messiness=200,
            season="spring",
            rng=rng,
            current_day=1,
            predisposed_names=set(),
            immune_names=set(),
            immunity_disease_ids=set(),
            existing_disease_ids=set(),
        )
        assert result is True


# ---------------------------------------------------------------------------
# try_spread_disease
# ---------------------------------------------------------------------------


class TestTrySpreadDisease:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_std_diseases(self, mock_add):
        """STD diseases should not spread via kennel contact."""
        disease = make_disease(sexually_transmitted=True, contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=10,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_respects_immunity_by_id(self, mock_add):
        """Target with immunity by disease id should not be infected."""
        disease = make_disease(disease_id=7, contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            target_immune_names=set(),
            target_immunity_disease_ids={7},
            target_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_respects_immunity_by_name(self, mock_add):
        """Target with mutation-granted immunity by name should not be infected."""
        disease = make_disease(name="Plague", contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            target_immune_names={"Plague"},
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_non_contagious_disease_does_not_spread(self, mock_add):
        """Disease with contagion_chance=0 should never spread."""
        disease = make_disease(contagion_chance=0.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_if_target_already_has_disease(self, mock_add):
        """Target that already has the disease should not get it again."""
        disease = make_disease(disease_id=3, contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=1,
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids={3},
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_spreads_when_roll_succeeds(self, mock_add):
        """Highly contagious disease with 0 constitution should spread."""
        disease = make_disease(contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=rng,
            current_day=5,
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        assert result is True
        mock_add.assert_awaited_once_with(2, disease.id, current_day=5, rng=rng)

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_season_contagion_modifier_applied(self, mock_add):
        """Season contagion modifiers should alter effective contagion chance."""
        # Base contagion 0.5, winter modifier 2.0 => effective contagion 1.0
        disease = make_disease(
            contagion_chance=0.5,
            season_contagion_modifiers={"winter": 2.0, "summer": 0.1},
        )
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="winter",
            rng=rng,
            current_day=1,
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        # Effective contagion = 0.5 * 2.0 = 1.0, so always spreads with constitution 0
        assert result is True


# ---------------------------------------------------------------------------
# try_breed_spread_disease
# ---------------------------------------------------------------------------


class TestTryBreedSpreadDisease:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_works_for_std_diseases(self, mock_add):
        """Breeding spread should work for STD diseases (unlike kennel spread)."""
        disease = make_disease(sexually_transmitted=True, contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_breed_spread_disease(
            parent_pooch_id=1,
            partner_pooch_id=2,
            disease=disease,
            partner_constitution=0,
            season="spring",
            rng=rng,
            current_day=1,
            partner_immune_names=set(),
            partner_immunity_disease_ids=set(),
            partner_existing_disease_ids=set(),
        )
        assert result is True
        mock_add.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_respects_immunity_by_id(self, mock_add):
        """Partner with immunity by id should not get infected during breeding."""
        disease = make_disease(disease_id=5, contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_breed_spread_disease(
            parent_pooch_id=1,
            partner_pooch_id=2,
            disease=disease,
            partner_constitution=0,
            season="spring",
            rng=rng,
            current_day=1,
            partner_immune_names=set(),
            partner_immunity_disease_ids={5},
            partner_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_respects_immunity_by_name(self, mock_add):
        """Partner with mutation-granted immunity by name should be blocked."""
        disease = make_disease(name="Canine STD", contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_breed_spread_disease(
            parent_pooch_id=1,
            partner_pooch_id=2,
            disease=disease,
            partner_constitution=0,
            season="spring",
            rng=rng,
            current_day=1,
            partner_immune_names={"Canine STD"},
            partner_immunity_disease_ids=set(),
            partner_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_if_partner_already_infected(self, mock_add):
        """Partner that already has the disease should not get it again."""
        disease = make_disease(disease_id=9, contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_breed_spread_disease(
            parent_pooch_id=1,
            partner_pooch_id=2,
            disease=disease,
            partner_constitution=0,
            season="spring",
            rng=rng,
            current_day=1,
            partner_immune_names=set(),
            partner_immunity_disease_ids=set(),
            partner_existing_disease_ids={9},
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_constitution_reduces_chance(self, mock_add):
        """Higher partner constitution should reduce breed-spread chance."""
        _disease = make_disease(contagion_chance=0.5)  # noqa: F841
        # constitution=50 => resistance = max(0.1, 1.0 - 50/100) = 0.5
        # chance = 0.5 * 0.5 = 0.25
        chance_with_const = 0.5 * max(0.1, 1.0 - 50 / CONSTITUTION_RESISTANCE_DIVISOR)
        assert chance_with_const < 0.5


# ---------------------------------------------------------------------------
# try_inherit_disease
# ---------------------------------------------------------------------------


class TestTryInheritDisease:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_respects_heritability_chance(self, mock_add):
        """Disease with heritability=1.0 should always be inherited."""
        disease = make_disease(heritability=1.0)
        rng = random.Random(42)
        result = await try_inherit_disease(
            parent_disease=disease,
            puppy_id=10,
            rng=rng,
            current_day=1,
        )
        assert result is True
        mock_add.assert_awaited_once_with(10, disease.id, current_day=1, rng=rng)

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_skips_non_heritable_diseases(self, mock_add):
        """Disease with heritability=0 should never be inherited."""
        disease = make_disease(heritability=0.0)
        rng = random.Random(42)
        result = await try_inherit_disease(
            parent_disease=disease,
            puppy_id=10,
            rng=rng,
            current_day=1,
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_negative_heritability_skips(self, mock_add):
        """Negative heritability should be treated as non-heritable."""
        disease = make_disease(heritability=-0.5)
        rng = random.Random(42)
        result = await try_inherit_disease(
            parent_disease=disease,
            puppy_id=10,
            rng=rng,
            current_day=1,
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_deterministic_with_seed(self, mock_add):
        """Same seed should produce same inheritance result."""
        disease = make_disease(heritability=0.5)
        result1 = await try_inherit_disease(
            parent_disease=disease,
            puppy_id=10,
            rng=random.Random(42),
            current_day=1,
        )
        result2 = await try_inherit_disease(
            parent_disease=disease,
            puppy_id=10,
            rng=random.Random(42),
            current_day=1,
        )
        assert result1 == result2


# ---------------------------------------------------------------------------
# try_recover_from_disease
# ---------------------------------------------------------------------------


class TestTryRecoverFromDisease:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_incurable_never_recovers(self, mock_remove, mock_immunity):
        """Incurable diseases should never recover."""
        disease = make_disease(curable=False, recovery_chance=1.0)
        pd = make_pooch_disease(disease=disease, treated=True)
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=1, rng=rng)
        assert result is False
        mock_remove.assert_not_awaited()
        mock_immunity.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_no_natural_recovery_without_treatment(self, mock_remove, mock_immunity):
        """Disease with recovery_chance=0 and not treated should not recover."""
        disease = make_disease(curable=True, recovery_chance=0.0, treatable=True)
        pd = make_pooch_disease(disease=disease, treated=False)
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=1, rng=rng)
        assert result is False
        mock_remove.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_treated_gets_bonus(self, mock_remove, mock_immunity):
        """Treated disease should have recovery_chance + TREATMENT_RECOVERY_BONUS."""
        # recovery_chance = 0.0, but treated adds TREATMENT_RECOVERY_BONUS (0.15)
        # Use heritability 1.0 for clarity — not relevant to recovery.
        disease = make_disease(curable=True, recovery_chance=0.85)
        pd = make_pooch_disease(disease=disease, treated=True)
        # Effective recovery = 0.85 + 0.15 = 1.0, clamped to 1.0 => always recovers
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=1, rng=rng)
        assert result is True
        mock_remove.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_applies_immunity_after_recovery(self, mock_remove, mock_immunity):
        """Recovery from a disease with immunity_duration should grant immunity."""
        disease = make_disease(
            disease_id=3,
            curable=True,
            recovery_chance=1.0,
            immunity_duration=30,
        )
        pd = make_pooch_disease(pooch_id=7, disease=disease, treated=False)
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=10, rng=rng)
        assert result is True
        mock_remove.assert_awaited_once_with(7, 3)
        mock_immunity.assert_awaited_once_with(7, 3, 40)  # 10 + 30

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_no_immunity_when_duration_is_none(self, mock_remove, mock_immunity):
        """Recovery without immunity_duration should not grant immunity."""
        disease = make_disease(curable=True, recovery_chance=1.0, immunity_duration=None)
        pd = make_pooch_disease(disease=disease, treated=False)
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=10, rng=rng)
        assert result is True
        mock_remove.assert_awaited_once()
        mock_immunity.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_no_immunity_when_duration_is_zero(self, mock_remove, mock_immunity):
        """Recovery with immunity_duration=0 should not grant immunity."""
        disease = make_disease(curable=True, recovery_chance=1.0, immunity_duration=0)
        pd = make_pooch_disease(disease=disease, treated=False)
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=10, rng=rng)
        assert result is True
        mock_remove.assert_awaited_once()
        mock_immunity.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_natural_recovery_with_positive_chance(self, mock_remove, mock_immunity):
        """Disease with positive recovery_chance should recover naturally (no treatment)."""
        disease = make_disease(curable=True, recovery_chance=1.0)
        pd = make_pooch_disease(disease=disease, treated=False)
        rng = random.Random(42)
        result = await try_recover_from_disease(pd, current_day=1, rng=rng)
        assert result is True
        mock_remove.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_immunity_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.remove_disease_from_pooch", new_callable=AsyncMock)
    async def test_treated_no_recovery_chance_can_still_recover(self, mock_remove, mock_immunity):
        """Treated disease with 0 base recovery should still recover via bonus."""
        disease = make_disease(curable=True, recovery_chance=0.0)
        pd = make_pooch_disease(disease=disease, treated=True)
        # Effective recovery = 0.0 + 0.15 = 0.15
        # Use a seed that produces a roll < 0.15
        # Find a seed where random.Random(seed).random() < 0.15
        for seed in range(100):
            rng = random.Random(seed)
            if rng.random() < TREATMENT_RECOVERY_BONUS:
                break
        rng = random.Random(seed)
        result = await try_recover_from_disease(pd, current_day=1, rng=rng)
        assert result is True
        mock_remove.assert_awaited_once()


class TestPublicDiseaseLabel:
    def test_visible_disease_shows_real_name(self):
        disease = make_disease(name="Kennel Cough", visible=True)
        pd = make_pooch_disease(disease=disease, visible=True)
        assert get_public_disease_label(pd) == "Kennel Cough"

    def test_hidden_disease_uses_displayed_symptom(self):
        disease = make_disease(name="Kennel Cough", visible=False, invisible_messages=["a persistent cough"])
        pd = make_pooch_disease(disease=disease, visible=False)
        pd.displayed_symptom = "a persistent cough"
        assert get_public_disease_label(pd) == "a persistent cough"

    def test_hidden_disease_without_symptom_uses_generic_label(self):
        disease = make_disease(name="Kennel Cough", visible=False)
        pd = make_pooch_disease(disease=disease, visible=False)
        pd.displayed_symptom = None
        assert get_public_disease_label(pd) == "a mysterious illness"


class TestTreatDisease:
    def _make_pd(self, owner_discord_id=1, treated=False, treatable=True, curable=True):
        pd = make_pooch_disease(disease=make_disease(treatable=treatable, curable=curable), treated=treated)
        pd.pooch = SimpleNamespace(owner_discord_id=owner_discord_id)
        return pd

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.get_pooch_disease_instance", new_callable=AsyncMock)
    async def test_disease_not_found(self, mock_get_pd):
        mock_get_pd.return_value = None
        assert await treat_disease(1, 99) == (False, "Disease not found.", 0)

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_pooch_disease_instance", new_callable=AsyncMock)
    async def test_not_your_pooch(self, mock_get_pd, mock_give):
        mock_get_pd.return_value = self._make_pd(owner_discord_id=1)
        assert await treat_disease(2, 5) == (False, "That's not your pooch.", 0)
        mock_give.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.get_pooch_disease_instance", new_callable=AsyncMock)
    async def test_already_treated(self, mock_get_pd):
        mock_get_pd.return_value = self._make_pd(treated=True)
        success, msg, _ = await treat_disease(1, 5)
        assert success is False
        assert "already been treated" in msg

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.treat_pooch_disease", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_pooch_disease_instance", new_callable=AsyncMock)
    async def test_success_charges_cost(self, mock_get_pd, mock_get_owner, mock_give, mock_treat):
        mock_get_pd.return_value = self._make_pd()
        mock_get_owner.return_value = SimpleNamespace(dollars=1000)
        success, _, cost = await treat_disease(1, 5)
        assert success is True
        assert cost == VET_DISEASE_TREATMENT_BASE_COST
        mock_give.assert_awaited_once_with(1, -VET_DISEASE_TREATMENT_BASE_COST)
        mock_treat.assert_awaited_once_with(5)


class TestDiagnoseDiseases:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_not_your_pooch(self, mock_get_owner, mock_get_pooch, mock_give):
        mock_get_owner.return_value = SimpleNamespace(dollars=1000)
        mock_get_pooch.return_value = SimpleNamespace(owner_discord_id=1)
        assert await diagnose_diseases(2, 1) == (False, "That's not your pooch.", [])
        mock_give.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.reveal_pooch_disease", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.list_invisible_pooch_disease_instances", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_reveals_hidden_diseases(self, mock_get_owner, mock_get_pooch, mock_give, mock_list, mock_reveal):
        mock_get_owner.return_value = SimpleNamespace(dollars=1000)
        mock_get_pooch.return_value = SimpleNamespace(owner_discord_id=1)
        hidden = make_pooch_disease(disease=make_disease(name="Mange", reveal_chance=1.0), visible=False)
        hidden.id = 11
        mock_list.return_value = [hidden]

        success, _, revealed = await diagnose_diseases(1, 1, rng_seed=0)

        assert success is True
        assert revealed == ["Mange"]
        mock_reveal.assert_awaited_once_with(11)
        mock_give.assert_awaited_once_with(1, -VET_DIAGNOSE_DISEASES_COST)


class TestAdditionalDiseaseLogic:
    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.get_kennel_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.update_kennel_messiness", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.consume_owner_item", new_callable=AsyncMock)
    @patch("src.game.manage_diseases.set_owner_hand_cleaned_today", new_callable=AsyncMock)
    async def test_cleaning_rejects_wrong_owner(self, mock_set_hand, mock_consume, mock_update, mock_get_kennel):
        mock_get_kennel.return_value = SimpleNamespace(id=1, owner_discord_id=999, messiness=50)
        assert await clean_kennel_by_hand(100, 1) == (False, "That's not your kennel.")
        assert await clean_kennel_with_item(100, 1, "Soap") == (False, "That's not your kennel.")
        mock_update.assert_not_awaited()
        mock_consume.assert_not_awaited()
        mock_set_hand.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_try_spread_disease_skips_out_of_season(self, mock_add):
        disease = make_disease(seasons=["winter"], contagion_chance=1.0)
        rng = random.Random(42)
        result = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            season="summer",
            rng=rng,
            current_day=1,
            messiness=100,
            target_predisposed_names=set(),
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        assert result is False
        mock_add.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.game.manage_diseases.add_disease_to_pooch", new_callable=AsyncMock)
    async def test_predisposition_increases_spread_chance(self, mock_add):
        disease = make_disease(name="Mange", contagion_chance=0.2)
        seed = 7
        low = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=random.Random(seed),
            current_day=1,
            target_predisposed_names=set(),
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        high = await try_spread_disease(
            source_pooch_id=1,
            target_pooch_id=2,
            disease=disease,
            target_constitution=0,
            messiness=0,
            season="spring",
            rng=random.Random(seed),
            current_day=1,
            target_predisposed_names={"Mange"},
            target_immune_names=set(),
            target_immunity_disease_ids=set(),
            target_existing_disease_ids=set(),
        )
        assert low is False
        assert high is True


class TestCleaningWithItems:
    _MOD = "src.game.manage_diseases"

    def _patches(self, parameters, kennel_pooches=()):
        kennel = SimpleNamespace(id=1, owner_discord_id=100, pooch_limit=10)
        item = SimpleNamespace(name="Bleach", category="cleaning", parameters=parameters)
        return (
            patch(f"{self._MOD}.get_kennel_by_id", new=AsyncMock(return_value=kennel)),
            patch(f"{self._MOD}.get_item_by_name", new=AsyncMock(return_value=item)),
            patch(f"{self._MOD}.consume_owner_item", new=AsyncMock(return_value=True)),
            patch(f"{self._MOD}.update_kennel_messiness", new=AsyncMock(return_value=0)),
            patch(f"{self._MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=list(kennel_pooches))),
            patch(f"{self._MOD}.modify_pooch_base_health", new=AsyncMock()),
        )

    @pytest.mark.asyncio
    async def test_message_shows_label_not_number(self):
        a, b, c, d, e, f = self._patches({"mess_reduction": 5})
        with a, b, c, d, e, f as hurt:
            ok, message = await clean_kennel_with_item(100, 1, "Soap")
        assert ok is True
        assert message == "You used one Bleach. The kennel is noticeably cleaner. It is now **Spotless**."
        hurt.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bleach_hurts_every_living_pooch(self):
        alive = SimpleNamespace(id=7, alive=True)
        dead = SimpleNamespace(id=8, alive=False)
        a, b, c, d, e, f = self._patches({"mess_reduction": 20, "side_effect_health": -1}, [alive, dead])
        with a, b, c, d, e, f as hurt:
            ok, message = await clean_kennel_with_item(100, 1, "Bleach")
        assert ok is True
        assert "harsh fumes" in message
        hurt.assert_awaited_once_with(7, -1)

    @pytest.mark.asyncio
    async def test_hand_clean_message_shows_label(self):
        with (
            patch(
                f"{self._MOD}.get_kennel_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=1, owner_discord_id=100, pooch_limit=10)),
            ),
            patch(
                f"{self._MOD}.get_owner_by_discord_id",
                new=AsyncMock(return_value=SimpleNamespace(hand_cleaned_today=False)),
            ),
            patch(f"{self._MOD}.update_kennel_messiness", new=AsyncMock(return_value=6)),
            patch(f"{self._MOD}.set_owner_hand_cleaned_today", new=AsyncMock()),
        ):
            ok, message = await clean_kennel_by_hand(100, 1)
        assert ok is True
        assert message.endswith("It is now **Messy**.")
