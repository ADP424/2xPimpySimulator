import pytest

from src.game.models.mutation import Mutation
from src.game.models.server import Server
from src.game.models.vendor import Vendor


def _make_mutation(id: int, name: str) -> Mutation:
    return Mutation(
        id=id,
        name=name,
        alt_name="",
        category="test",
        description="",
        heritability=0.5,
        health_impact="low",
        rarity="common",
        affects_females=True,
        affects_males=True,
    )


class TestVendorCreation:
    def test_basic_creation(self):
        vendor = Vendor(
            id=1,
            server_discord_id=999,
            name="Barks & Bites",
            price_markup=1.5,
            stock_count=3,
            desired_mutations=[],
            desired_breeds=[],
            server=None,
        )
        assert vendor.id == 1
        assert vendor.server_discord_id == 999
        assert vendor.name == "Barks & Bites"
        assert vendor.price_markup == 1.5
        assert vendor.stock_count == 3
        assert vendor.desired_mutations == []
        assert vendor.server is None

    def test_with_mutations(self):
        m1 = _make_mutation(1, "Cataracts")
        m2 = _make_mutation(2, "Sickle Cell")
        vendor = Vendor(
            id=1,
            server_discord_id=999,
            name="Shop",
            price_markup=1.0,
            stock_count=0,
            desired_mutations=[m1, m2],
            desired_breeds=[],
            server=None,
        )
        assert vendor.desired_mutations[0].name == "Cataracts"
        assert vendor.desired_mutations[1].name == "Sickle Cell"

    def test_with_server(self):
        server = Server(discord_id=999, event_channel_discord_id=888)
        vendor = Vendor(
            id=1,
            server_discord_id=999,
            name="Shop",
            price_markup=1.0,
            stock_count=0,
            desired_mutations=[],
            desired_breeds=[],
            server=server,
        )
        assert vendor.server is not None
        assert vendor.server.discord_id == 999

    def test_frozen(self):
        vendor = Vendor(
            id=1,
            server_discord_id=999,
            name="Shop",
            price_markup=1.0,
            stock_count=0,
            desired_mutations=[],
            desired_breeds=[],
            server=None,
        )
        with pytest.raises(AttributeError):
            vendor.name = "Changed"  # type: ignore[misc]

    def test_equality(self):
        args = dict(
            id=1,
            server_discord_id=999,
            name="Shop",
            price_markup=1.0,
            stock_count=0,
            desired_mutations=[],
            desired_breeds=[],
            server=None,
        )
        assert Vendor(**args) == Vendor(**args)

    def test_zero_markup(self):
        vendor = Vendor(
            id=1,
            server_discord_id=999,
            name="Charity Shop",
            price_markup=0.0,
            stock_count=5,
            desired_mutations=[],
            desired_breeds=[],
            server=None,
        )
        assert vendor.price_markup == 0.0
