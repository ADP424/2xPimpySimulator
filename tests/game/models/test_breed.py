from unittest.mock import MagicMock

import pytest

from src.game.models import Breed, to_breed


class TestBreedCreation:
    def test_basic_creation(self):
        breed = Breed(
            id=1,
            name="Labrador Retriever",
            alt_name="Lab",
            category="retriever",
            description="A friendly dog",
            rarity="common",
            min_size=20,
            max_size=30,
        )
        assert breed.id == 1
        assert breed.name == "Labrador Retriever"
        assert breed.alt_name == "Lab"
        assert breed.category == "retriever"
        assert breed.description == "A friendly dog"
        assert breed.rarity == "common"
        assert breed.min_size == 20
        assert breed.max_size == 30

    def test_empty_alt_name(self):
        breed = Breed(
            id=2, name="Pug", alt_name="", category="toy", description="", rarity="rare", min_size=1, max_size=5
        )
        assert breed.alt_name == ""

    def test_frozen(self):
        breed = Breed(
            id=1,
            name="Lab",
            alt_name="",
            category="retriever",
            description="",
            rarity="common",
            min_size=10,
            max_size=20,
        )
        with pytest.raises(AttributeError):
            breed.name = "Changed"  # type: ignore[misc]

    def test_equality(self):
        args = dict(
            id=1,
            name="Lab",
            alt_name="",
            category="retriever",
            description="",
            rarity="common",
            min_size=10,
            max_size=20,
        )
        assert Breed(**args) == Breed(**args)

    def test_inequality(self):
        b1 = Breed(
            id=1,
            name="Lab",
            alt_name="",
            category="retriever",
            description="",
            rarity="common",
            min_size=10,
            max_size=20,
        )
        b2 = Breed(id=2, name="Pug", alt_name="", category="toy", description="", rarity="rare", min_size=1, max_size=5)
        assert b1 != b2


class TestToBreed:
    async def test_converts_orm_to_breed(self):
        orm = MagicMock()
        orm.id = 42
        orm.name = "Greyhound"
        orm.alt_name = "Grey"
        orm.category = "sighthound"
        orm.description = "Fast runner"
        orm.rarity = "uncommon"
        orm.min_size = 15
        orm.max_size = 25

        result = await to_breed(orm)
        assert isinstance(result, Breed)
        assert result.id == 42
        assert result.name == "Greyhound"
        assert result.alt_name == "Grey"
        assert result.category == "sighthound"
        assert result.description == "Fast runner"
        assert result.rarity == "uncommon"
        assert result.min_size == 15
        assert result.max_size == 25
