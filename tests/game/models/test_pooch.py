from datetime import datetime
from types import SimpleNamespace

import pytest

from src.game.models import (
    Pooch,
    PoochBreedInfo,
    get_breeding_status,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pooch(**overrides) -> Pooch:
    """Build a Pooch dataclass with sensible defaults, overridable via kwargs."""
    defaults = dict(
        id=1,
        name="Test",
        age=2,
        sex="male",
        base_health=10,
        health_loss_age=0,
        strength=10,
        cuteness=10,
        fluffiness=10,
        intelligence=10,
        dexterity=10,
        fertility=10,
        aggressiveness=10,
        constitution=10,
        breeding_cooldown=0,
        alive=True,
        virgin=True,
        vet_checked=False,
        owner_discord_id=None,
        vendor_id=None,
        created_at=None,
        size=10,
        health=10,
        mood=None,
        owner=None,
        vendor=None,
        breeds=[],
        mutations=[],
        injuries=[],
        diseases=[],
    )
    defaults.update(overrides)
    return Pooch(**defaults)


# ===========================================================================


class TestPoochStatus:
    def test_dead_pooch(self):
        p = _make_pooch(alive=False, age=2, health=10)
        assert p.status == "dead"

    def test_dead_takes_priority_over_old(self):
        p = _make_pooch(alive=False, age=15, health=10)
        assert p.status == "dead"

    def test_dead_takes_priority_over_sick(self):
        p = _make_pooch(alive=False, age=2, health=1)
        assert p.status == "dead"

    def test_old_pooch(self):
        p = _make_pooch(alive=True, age=12, health=10)
        assert p.status == "old"

    def test_old_pooch_exact_boundary(self):
        p = _make_pooch(alive=True, age=12, health=10)
        assert p.status == "old"

    def test_old_pooch_well_above(self):
        p = _make_pooch(alive=True, age=20, health=10)
        assert p.status == "old"

    def test_old_takes_priority_over_sick(self):
        p = _make_pooch(alive=True, age=15, health=3)
        assert p.status == "old"

    def test_sick_pooch(self):
        p = _make_pooch(alive=True, age=2, health=3)
        assert p.status == "sick"

    def test_sick_exact_boundary(self):
        p = _make_pooch(alive=True, age=2, health=5)
        assert p.status == "sick"

    def test_sick_health_one(self):
        p = _make_pooch(alive=True, age=2, health=1)
        assert p.status == "sick"

    def test_healthy_pooch(self):
        p = _make_pooch(alive=True, age=2, health=10)
        assert p.status == "healthy"

    def test_healthy_just_above_sick(self):
        p = _make_pooch(alive=True, age=2, health=6)
        assert p.status == "healthy"

    def test_healthy_just_below_old(self):
        p = _make_pooch(alive=True, age=11, health=10)
        assert p.status == "healthy"


class TestPoochBreedingStatus:
    @pytest.mark.parametrize(
        "cooldown, expected",
        [(0, "in_heat"), (1, "heating_up"), (5, "heating_up"), (6, "cooled"), (10, "cooled")],
    )
    def test_get_breeding_status(self, cooldown, expected):
        assert get_breeding_status(cooldown) == expected

    def test_breeding_status_property(self):
        assert _make_pooch(breeding_cooldown=3).breeding_status == "heating_up"

    def test_can_breed_when_alive_and_in_heat(self):
        assert _make_pooch(alive=True, breeding_cooldown=0).can_breed is True

    def test_cannot_breed_on_cooldown(self):
        assert _make_pooch(alive=True, breeding_cooldown=1).can_breed is False

    def test_cannot_breed_when_dead(self):
        assert _make_pooch(alive=False, breeding_cooldown=0).can_breed is False


# ===========================================================================
# Pooch.birthday
# ===========================================================================


class TestPoochBirthday:
    def test_birthday_returns_created_at_minus_age(self):
        from datetime import timedelta

        dt = datetime(2025, 1, 15, 12, 0, 0)
        p = _make_pooch(created_at=dt)  # age=2 by default
        assert p.birthday == dt - timedelta(days=2)

    def test_birthday_age_zero(self):
        dt = datetime(2025, 1, 15, 12, 0, 0)
        p = _make_pooch(created_at=dt, age=0)
        assert p.birthday == dt

    def test_birthday_none_when_created_at_none(self):
        p = _make_pooch(created_at=None)
        assert p.birthday is None


# ===========================================================================
# PoochBreedInfo
# ===========================================================================


class TestPoochBreedInfo:
    def test_creation(self):
        from src.game.models.breed import Breed

        breed = Breed(
            id=1,
            name="Pug",
            alt_name="",
            category="toy",
            description="A small dog",
            rarity="common",
            min_size=1,
            max_size=5,
        )
        info = PoochBreedInfo(breed=breed, relative_weight=0.75)
        assert info.breed.name == "Pug"
        assert info.relative_weight == 0.75

    def test_frozen(self):
        from src.game.models.breed import Breed

        breed = Breed(
            id=1, name="Pug", alt_name="", category="toy", description="", rarity="common", min_size=1, max_size=5
        )
        info = PoochBreedInfo(breed=breed, relative_weight=0.75)
        with pytest.raises(AttributeError):
            info.relative_weight = 1.0  # type: ignore[misc]


# ===========================================================================
# Pooch is frozen
# ===========================================================================


class TestPoochFrozen:
    def test_cannot_mutate(self):
        p = _make_pooch()
        with pytest.raises(AttributeError):
            p.name = "Changed"  # type: ignore[misc]


class TestToPoochHourlyFields:
    async def test_copies_hourly_tick_columns(self):
        from unittest.mock import AsyncMock, patch

        from src.game.models import to_pooch

        row = SimpleNamespace(
            id=7,
            name="Eternal",
            age=3,
            sex="female",
            base_health=10,
            health_loss_age=0,
            strength=10,
            cuteness=10,
            fluffiness=10,
            intelligence=10,
            dexterity=10,
            fertility=10,
            aggressiveness=10,
            constitution=10,
            size=10,
            breeding_cooldown=0,
            alive=True,
            virgin=False,
            vet_checked=False,
            mood=None,
            owner_discord_id=None,
            vendor_id=None,
            created_at=None,
            pregnancy_timer=12,
            rejuvenation_count=2,
            immortal=True,
            starvation=5,
            birth_hour=48,
            mess_output=3,
            consumption=2,
        )
        empty = AsyncMock(return_value=[])
        with patch.multiple(
            "src.game.models.pooch",
            list_pooch_breeds=empty,
            list_pooch_mutations=empty,
            list_pooch_mutation_instances=empty,
            list_pooch_injury_instances=empty,
            list_pooch_disease_instances=empty,
            get_pooch_health=AsyncMock(return_value=10),
        ):
            pooch = await to_pooch(row)

        assert (pooch.pregnancy_timer, pooch.rejuvenation_count, pooch.immortal, pooch.starvation) == (12, 2, True, 5)
        assert (pooch.birth_hour, pooch.mess_output, pooch.consumption) == (48, 3, 2)
