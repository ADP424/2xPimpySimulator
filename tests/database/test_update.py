"""Tests for src/database/update.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_scope(pooch=None, owner=None, kennel=None, mutations=None, scalars_all=None):
    """
    Build a fake session_scope whose session.execute returns a controllable result.
    """
    mock_session = AsyncMock()

    # Default entity returned by scalar_one_or_none
    entity = pooch or owner or kennel

    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = entity
    if scalars_all is not None:
        mock_response.scalars.return_value.all.return_value = scalars_all

    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.flush = AsyncMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _FakeScope, mock_session


class FakePooch:
    """Mutable stand-in for a Pooch ORM object."""

    def __init__(
        self, id=1, base_health=10, age=3, health_loss_age=0, breeding_cooldown=5, strength=10, alive=True, fertility=10
    ):
        self.id = id
        self.base_health = base_health
        self.age = age
        self.health_loss_age = health_loss_age
        self.breeding_cooldown = breeding_cooldown
        self.strength = strength
        self.alive = alive
        self.fertility = fertility


class FakeOwner:
    """Mutable stand-in for an Owner ORM object."""

    def __init__(self, discord_id=1, dollars=100, bloodskulls=5, bones=0, begged_today=False):
        self.discord_id = discord_id
        self.dollars = dollars
        self.bloodskulls = bloodskulls
        self.bones = bones
        self.begged_today = begged_today


class FakeKennel:
    """Mutable stand-in for a Kennel ORM object."""

    def __init__(self, id=1, pooch_limit=10, name="Kennel"):
        self.id = id
        self.pooch_limit = pooch_limit
        self.name = name


# ---------------------------------------------------------------------------
# modify_pooch_base_health
# ---------------------------------------------------------------------------


async def test_modify_pooch_base_health_adds_positive():
    """modify_pooch_base_health should increase base health."""
    fake_pooch = FakePooch(base_health=10)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_base_health

        result = await modify_pooch_base_health(1, 5)

    assert result.base_health == 15


async def test_modify_pooch_base_health_clamps_to_zero():
    """modify_pooch_base_health should not go below 0."""
    fake_pooch = FakePooch(base_health=3)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_base_health

        result = await modify_pooch_base_health(1, -10)

    assert result.base_health == 0


async def test_modify_pooch_base_health_returns_none_when_missing():
    """modify_pooch_base_health should return None when pooch doesn't exist."""
    scope_cls, _ = _mock_session_scope(pooch=None)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_base_health

        result = await modify_pooch_base_health(999, 5)

    assert result is None


# ---------------------------------------------------------------------------
# give_money_to_owner
# ---------------------------------------------------------------------------


async def test_give_money_to_owner_adds_dollars():
    """give_money_to_owner should add the given amount to the owner's dollars."""
    fake_owner = FakeOwner(dollars=100)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_money_to_owner

        result = await give_money_to_owner(1, 50)

    assert result.dollars == 150


async def test_give_money_to_owner_subtracts_dollars():
    """give_money_to_owner with negative should subtract."""
    fake_owner = FakeOwner(dollars=100)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_money_to_owner

        result = await give_money_to_owner(1, -30)

    assert result.dollars == 70


async def test_give_money_to_owner_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_money_to_owner

        result = await give_money_to_owner(999, 50)

    assert result is None


# ---------------------------------------------------------------------------
# give_bloodskulls_to_owner
# ---------------------------------------------------------------------------


async def test_give_bloodskulls_to_owner():
    fake_owner = FakeOwner(bloodskulls=5)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_bloodskulls_to_owner

        result = await give_bloodskulls_to_owner(1, 3)

    assert result.bloodskulls == 8


# ---------------------------------------------------------------------------
# give_bones_to_owner
# ---------------------------------------------------------------------------


async def test_give_bones_to_owner():
    fake_owner = FakeOwner(bones=0)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_bones_to_owner

        result = await give_bones_to_owner(1, 10)

    assert result.bones == 10


# ---------------------------------------------------------------------------
# age_pooch
# ---------------------------------------------------------------------------


async def test_age_pooch_increments_age():
    fake_pooch = FakePooch(age=3, health_loss_age=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import age_pooch

        result = await age_pooch(1)

    assert result.age == 4


async def test_age_pooch_increments_health_loss_when_old():
    """When age exceeds health_loss_starting_age, health_loss_age should increment."""
    fake_pooch = FakePooch(age=5, health_loss_age=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import age_pooch

        result = await age_pooch(1, health_loss_starting_age=5)

    assert result.age == 6
    assert result.health_loss_age == 1


async def test_age_pooch_no_health_loss_when_young():
    """When age is below health_loss_starting_age, health_loss_age stays at 0."""
    fake_pooch = FakePooch(age=2, health_loss_age=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import age_pooch

        result = await age_pooch(1, health_loss_starting_age=5)

    assert result.age == 3
    assert result.health_loss_age == 0


# ---------------------------------------------------------------------------
# decrement_pooch_breeding_cooldown
# ---------------------------------------------------------------------------


async def test_decrement_pooch_breeding_cooldown():
    fake_pooch = FakePooch(breeding_cooldown=3)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import decrement_pooch_breeding_cooldown

        result = await decrement_pooch_breeding_cooldown(1)

    assert result.breeding_cooldown == 2


async def test_decrement_pooch_breeding_cooldown_clamps_at_zero():
    fake_pooch = FakePooch(breeding_cooldown=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import decrement_pooch_breeding_cooldown

        result = await decrement_pooch_breeding_cooldown(1)

    assert result.breeding_cooldown == 0


# ---------------------------------------------------------------------------
# set_pooch_breeding_cooldown
# ---------------------------------------------------------------------------


async def test_set_pooch_breeding_cooldown():
    fake_pooch = FakePooch(breeding_cooldown=5)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_breeding_cooldown

        result = await set_pooch_breeding_cooldown(1, 10)

    assert result.breeding_cooldown == 10


async def test_set_pooch_breeding_cooldown_clamps_negative():
    fake_pooch = FakePooch(breeding_cooldown=5)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_breeding_cooldown

        result = await set_pooch_breeding_cooldown(1, -3)

    assert result.breeding_cooldown == 0


# ---------------------------------------------------------------------------
# reset_pooch_breeding_cooldown
# ---------------------------------------------------------------------------


async def test_reset_pooch_breeding_cooldown_with_no_mutations():
    """With no mutations, cooldown should be set to base_cooldown."""
    fake_pooch = FakePooch(breeding_cooldown=0)
    mock_session = AsyncMock()

    # First call: pooch lookup
    pooch_response = MagicMock()
    pooch_response.scalar_one_or_none.return_value = fake_pooch

    # Second call: mutations query
    mutation_response = MagicMock()
    mutation_response.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[pooch_response, mutation_response])

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_pooch_breeding_cooldown

        result = await reset_pooch_breeding_cooldown(1, base_cooldown=5)

    assert result.breeding_cooldown == 5


async def test_reset_pooch_breeding_cooldown_with_mutation_add():
    """Mutations with breeding_cooldown parameter should adjust the final value."""
    fake_pooch = FakePooch(breeding_cooldown=0)
    fake_mutation = SimpleNamespace(parameters={"breeding_cooldown": 3})

    mock_session = AsyncMock()

    pooch_response = MagicMock()
    pooch_response.scalar_one_or_none.return_value = fake_pooch

    mutation_response = MagicMock()
    mutation_response.scalars.return_value.all.return_value = [fake_mutation]

    mock_session.execute = AsyncMock(side_effect=[pooch_response, mutation_response])

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_pooch_breeding_cooldown

        result = await reset_pooch_breeding_cooldown(1, base_cooldown=5)

    # (5 + 3) * 1.0 = 8
    assert result.breeding_cooldown == 8


async def test_reset_pooch_breeding_cooldown_with_multiplier():
    """A multiplier should be applied to the final cooldown."""
    fake_pooch = FakePooch(breeding_cooldown=0)

    mock_session = AsyncMock()

    pooch_response = MagicMock()
    pooch_response.scalar_one_or_none.return_value = fake_pooch

    mutation_response = MagicMock()
    mutation_response.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[pooch_response, mutation_response])

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_pooch_breeding_cooldown

        result = await reset_pooch_breeding_cooldown(1, base_cooldown=10, multiplier=0.5)

    # (10 + 0) * 0.5 = 5.0 -> round = 5
    assert result.breeding_cooldown == 5


async def test_reset_pooch_breeding_cooldown_clamps_to_zero():
    """Negative mutation adjustments should not push cooldown below 0."""
    fake_pooch = FakePooch(breeding_cooldown=0)
    fake_mutation = SimpleNamespace(parameters={"breeding_cooldown": -100})

    mock_session = AsyncMock()

    pooch_response = MagicMock()
    pooch_response.scalar_one_or_none.return_value = fake_pooch

    mutation_response = MagicMock()
    mutation_response.scalars.return_value.all.return_value = [fake_mutation]

    mock_session.execute = AsyncMock(side_effect=[pooch_response, mutation_response])

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_pooch_breeding_cooldown

        result = await reset_pooch_breeding_cooldown(1, base_cooldown=2)

    assert result.breeding_cooldown == 0


# ---------------------------------------------------------------------------
# modify_kennel_pooch_limit
# ---------------------------------------------------------------------------


async def test_modify_kennel_pooch_limit():
    fake_kennel = FakeKennel(pooch_limit=10)
    scope_cls, _ = _mock_session_scope(kennel=fake_kennel)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_kennel_pooch_limit

        result = await modify_kennel_pooch_limit(1, 5)

    assert result.pooch_limit == 15


async def test_modify_kennel_pooch_limit_clamps_to_one():
    fake_kennel = FakeKennel(pooch_limit=3)
    scope_cls, _ = _mock_session_scope(kennel=fake_kennel)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_kennel_pooch_limit

        result = await modify_kennel_pooch_limit(1, -10)

    assert result.pooch_limit == 1


# ---------------------------------------------------------------------------
# set_pooch_dead / set_pooch_alive
# ---------------------------------------------------------------------------


async def test_set_pooch_dead():
    fake_pooch = FakePooch(alive=True)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_dead

        result = await set_pooch_dead(1)

    assert result.alive is False


async def test_set_pooch_alive():
    fake_pooch = FakePooch(alive=False)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_alive

        result = await set_pooch_alive(1)

    assert result.alive is True


# ---------------------------------------------------------------------------
# rename_pooch / rename_kennel
# ---------------------------------------------------------------------------


async def test_rename_pooch():
    fake_pooch = FakePooch()
    fake_pooch.name = "OldName"
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import rename_pooch

        result = await rename_pooch(1, "NewName")

    assert result.name == "NewName"


async def test_rename_kennel():
    fake_kennel = FakeKennel(name="Old")
    scope_cls, _ = _mock_session_scope(kennel=fake_kennel)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import rename_kennel

        result = await rename_kennel(1, "New")

    assert result.name == "New"


# ---------------------------------------------------------------------------
# set_owner_begged_today
# ---------------------------------------------------------------------------


async def test_set_owner_begged_today():
    fake_owner = FakeOwner(begged_today=False)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_begged_today

        result = await set_owner_begged_today(1, True)

    assert result.begged_today is True


# ---------------------------------------------------------------------------
# modify_pooch_strength
# ---------------------------------------------------------------------------


async def test_modify_pooch_strength():
    fake_pooch = FakePooch(strength=10)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_strength

        result = await modify_pooch_strength(1, 5)

    assert result.strength == 15


async def test_modify_pooch_strength_clamps_to_zero():
    fake_pooch = FakePooch(strength=3)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)

    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_strength

        result = await modify_pooch_strength(1, -10)

    assert result.strength == 0
