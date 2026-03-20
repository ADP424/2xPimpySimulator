from unittest.mock import MagicMock

import pytest

from src.game.models.mutation import Mutation, to_mutation


class TestMutationCreation:
    def test_basic_creation(self):
        m = Mutation(
            id=1,
            name="Cataracts",
            alt_name="Cloudy Eyes",
            category="blindness",
            description="Vision impairment",
            heritability=0.5,
            health_impact="moderate",
            rarity="uncommon",
            affects_females=True,
            affects_males=True,
        )
        assert m.id == 1
        assert m.name == "Cataracts"
        assert m.alt_name == "Cloudy Eyes"
        assert m.category == "blindness"
        assert m.description == "Vision impairment"
        assert m.heritability == 0.5
        assert m.health_impact == "moderate"
        assert m.rarity == "uncommon"
        assert m.affects_females is True
        assert m.affects_males is True

    def test_female_only_mutation(self):
        m = Mutation(
            id=2,
            name="PCOS",
            alt_name="Polycystic Ovary Syndrome",
            category="hormonal",
            description="Hormonal disorder",
            heritability=0.3,
            health_impact="moderate",
            rarity="rare",
            affects_females=True,
            affects_males=False,
        )
        assert m.affects_females is True
        assert m.affects_males is False

    def test_zero_heritability(self):
        m = Mutation(
            id=3,
            name="Trauma",
            alt_name="",
            category="acquired",
            description="",
            heritability=0.0,
            health_impact="low",
            rarity="common",
            affects_females=True,
            affects_males=True,
        )
        assert m.heritability == 0.0

    def test_frozen(self):
        m = Mutation(
            id=1,
            name="Test",
            alt_name="",
            category="",
            description="",
            heritability=0.5,
            health_impact="low",
            rarity="common",
            affects_females=True,
            affects_males=True,
        )
        with pytest.raises(AttributeError):
            m.name = "Changed"  # type: ignore[misc]

    def test_equality(self):
        args = dict(
            id=1,
            name="Test",
            alt_name="",
            category="",
            description="",
            heritability=0.5,
            health_impact="low",
            rarity="common",
            affects_females=True,
            affects_males=True,
        )
        assert Mutation(**args) == Mutation(**args)


class TestToMutation:
    async def test_converts_orm_to_mutation(self):
        orm = MagicMock()
        orm.id = 10
        orm.name = "Sickle Cell"
        orm.alt_name = "SCA"
        orm.category = "blood"
        orm.description = "Blood disorder"
        orm.heritability = 0.8
        orm.health_impact = "severe"
        orm.rarity = "rare"
        orm.affects_females = True
        orm.affects_males = True

        result = await to_mutation(orm)
        assert isinstance(result, Mutation)
        assert result.id == 10
        assert result.name == "Sickle Cell"
        assert result.heritability == 0.8
        assert result.health_impact == "severe"
