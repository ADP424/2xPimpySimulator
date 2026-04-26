import pytest

from src.game.models.owner import Owner


class TestOwnerCreation:
    def test_basic_creation(self):
        owner = Owner(discord_id=123456, discord_name="Alice", dollars=100, bloodskulls=5, bones=10)
        assert owner.discord_id == 123456
        assert owner.discord_name == "Alice"
        assert owner.dollars == 100
        assert owner.bloodskulls == 5
        assert owner.bones == 10

    def test_none_discord_name(self):
        owner = Owner(discord_id=1, discord_name=None, dollars=0, bloodskulls=0, bones=0)
        assert owner.discord_name is None

    def test_zero_currencies(self):
        owner = Owner(discord_id=1, discord_name="Bob", dollars=0, bloodskulls=0, bones=0)
        assert owner.dollars == 0
        assert owner.bloodskulls == 0
        assert owner.bones == 0

    def test_negative_dollars(self):
        owner = Owner(discord_id=1, discord_name="Broke Bob", dollars=-50, bloodskulls=0, bones=0)
        assert owner.dollars == -50

    def test_frozen(self):
        owner = Owner(discord_id=1, discord_name="Test", dollars=0, bloodskulls=0, bones=0)
        with pytest.raises(AttributeError):
            owner.dollars = 999  # type: ignore[misc]

    def test_equality(self):
        o1 = Owner(discord_id=1, discord_name="A", dollars=10, bloodskulls=0, bones=0)
        o2 = Owner(discord_id=1, discord_name="A", dollars=10, bloodskulls=0, bones=0)
        assert o1 == o2

    def test_inequality_different_id(self):
        o1 = Owner(discord_id=1, discord_name="A", dollars=10, bloodskulls=0, bones=0)
        o2 = Owner(discord_id=2, discord_name="A", dollars=10, bloodskulls=0, bones=0)
        assert o1 != o2
