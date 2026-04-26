import pytest

from src.game.models.kennel import Kennel
from src.game.models.owner import Owner


class TestKennelCreation:
    def test_basic_creation(self):
        kennel = Kennel(id=1, owner_discord_id=123, name="Happy Paws", pooch_limit=5, owner=None)
        assert kennel.id == 1
        assert kennel.owner_discord_id == 123
        assert kennel.name == "Happy Paws"
        assert kennel.pooch_limit == 5
        assert kennel.owner is None

    def test_with_owner(self):
        owner = Owner(discord_id=123, discord_name="Alice", dollars=100, bloodskulls=0, bones=0)
        kennel = Kennel(id=1, owner_discord_id=123, name="Happy Paws", pooch_limit=5, owner=owner)
        assert kennel.owner is not None
        assert kennel.owner.discord_name == "Alice"

    def test_frozen(self):
        kennel = Kennel(id=1, owner_discord_id=123, name="Test", pooch_limit=5, owner=None)
        with pytest.raises(AttributeError):
            kennel.name = "Changed"  # type: ignore[misc]

    def test_equality(self):
        k1 = Kennel(id=1, owner_discord_id=123, name="Test", pooch_limit=5, owner=None)
        k2 = Kennel(id=1, owner_discord_id=123, name="Test", pooch_limit=5, owner=None)
        assert k1 == k2

    def test_inequality(self):
        k1 = Kennel(id=1, owner_discord_id=123, name="Test", pooch_limit=5, owner=None)
        k2 = Kennel(id=2, owner_discord_id=456, name="Other", pooch_limit=10, owner=None)
        assert k1 != k2

    def test_default_pooch_limit(self):
        kennel = Kennel(id=1, owner_discord_id=123, name="Starter", pooch_limit=3, owner=None)
        assert kennel.pooch_limit == 3
