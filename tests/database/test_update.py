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


async def test_modify_pooch_strength_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_strength

        result = await modify_pooch_strength(999, 5)
    assert result is None


# ---------------------------------------------------------------------------
# set_pooch_strength
# ---------------------------------------------------------------------------


async def test_set_pooch_strength():
    fake_pooch = FakePooch(strength=5)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_strength

        result = await set_pooch_strength(1, 20)
    assert result.strength == 20


async def test_set_pooch_strength_clamps_negative():
    fake_pooch = FakePooch(strength=5)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_strength

        result = await set_pooch_strength(1, -5)
    assert result.strength == 0


async def test_set_pooch_strength_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_strength

        result = await set_pooch_strength(999, 5)
    assert result is None


# ---------------------------------------------------------------------------
# modify/set pooch cuteness
# ---------------------------------------------------------------------------


async def test_modify_pooch_cuteness():
    fake_pooch = FakePooch()
    fake_pooch.cuteness = 10
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_cuteness

        result = await modify_pooch_cuteness(1, 3)
    assert result.cuteness == 13


async def test_modify_pooch_cuteness_clamps_to_zero():
    fake_pooch = FakePooch()
    fake_pooch.cuteness = 2
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_cuteness

        result = await modify_pooch_cuteness(1, -10)
    assert result.cuteness == 0


async def test_set_pooch_cuteness():
    fake_pooch = FakePooch()
    fake_pooch.cuteness = 5
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_cuteness

        result = await set_pooch_cuteness(1, 15)
    assert result.cuteness == 15


# ---------------------------------------------------------------------------
# modify/set pooch fluffiness
# ---------------------------------------------------------------------------


async def test_modify_pooch_fluffiness():
    fake_pooch = FakePooch()
    fake_pooch.fluffiness = 4
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_fluffiness

        result = await modify_pooch_fluffiness(1, 6)
    assert result.fluffiness == 10


async def test_set_pooch_fluffiness():
    fake_pooch = FakePooch()
    fake_pooch.fluffiness = 4
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_fluffiness

        result = await set_pooch_fluffiness(1, 8)
    assert result.fluffiness == 8


# ---------------------------------------------------------------------------
# modify/set pooch intelligence
# ---------------------------------------------------------------------------


async def test_modify_pooch_intelligence():
    fake_pooch = FakePooch()
    fake_pooch.intelligence = 7
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_intelligence

        result = await modify_pooch_intelligence(1, 3)
    assert result.intelligence == 10


async def test_set_pooch_intelligence():
    fake_pooch = FakePooch()
    fake_pooch.intelligence = 7
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_intelligence

        result = await set_pooch_intelligence(1, 12)
    assert result.intelligence == 12


# ---------------------------------------------------------------------------
# modify/set pooch dexterity
# ---------------------------------------------------------------------------


async def test_modify_pooch_dexterity():
    fake_pooch = FakePooch()
    fake_pooch.dexterity = 5
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_dexterity

        result = await modify_pooch_dexterity(1, 4)
    assert result.dexterity == 9


async def test_set_pooch_dexterity():
    fake_pooch = FakePooch()
    fake_pooch.dexterity = 5
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_dexterity

        result = await set_pooch_dexterity(1, 11)
    assert result.dexterity == 11


# ---------------------------------------------------------------------------
# modify/set pooch fertility
# ---------------------------------------------------------------------------


async def test_modify_pooch_fertility():
    fake_pooch = FakePooch(fertility=6)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_fertility

        result = await modify_pooch_fertility(1, 4)
    assert result.fertility == 10


async def test_set_pooch_fertility():
    fake_pooch = FakePooch(fertility=6)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_fertility

        result = await set_pooch_fertility(1, 20)
    assert result.fertility == 20


# ---------------------------------------------------------------------------
# modify/set pooch aggressiveness
# ---------------------------------------------------------------------------


async def test_modify_pooch_aggressiveness():
    fake_pooch = FakePooch()
    fake_pooch.aggressiveness = 3
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_aggressiveness

        result = await modify_pooch_aggressiveness(1, 2)
    assert result.aggressiveness == 5


async def test_set_pooch_aggressiveness():
    fake_pooch = FakePooch()
    fake_pooch.aggressiveness = 3
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_aggressiveness

        result = await set_pooch_aggressiveness(1, 9)
    assert result.aggressiveness == 9


# ---------------------------------------------------------------------------
# modify/set pooch constitution
# ---------------------------------------------------------------------------


async def test_modify_pooch_constitution():
    fake_pooch = FakePooch()
    fake_pooch.constitution = 8
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_constitution

        result = await modify_pooch_constitution(1, 2)
    assert result.constitution == 10


async def test_set_pooch_constitution():
    fake_pooch = FakePooch()
    fake_pooch.constitution = 8
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_constitution

        result = await set_pooch_constitution(1, 14)
    assert result.constitution == 14


# ---------------------------------------------------------------------------
# modify_pooch_breeding_cooldown
# ---------------------------------------------------------------------------


async def test_modify_pooch_breeding_cooldown():
    fake_pooch = FakePooch(breeding_cooldown=5)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_breeding_cooldown

        result = await modify_pooch_breeding_cooldown(1, 3)
    assert result.breeding_cooldown == 8


async def test_modify_pooch_breeding_cooldown_clamps_to_zero():
    fake_pooch = FakePooch(breeding_cooldown=2)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_breeding_cooldown

        result = await modify_pooch_breeding_cooldown(1, -10)
    assert result.breeding_cooldown == 0


# ---------------------------------------------------------------------------
# modify_pooch_age / set_pooch_age / set_pooch_base_health
# ---------------------------------------------------------------------------


async def test_modify_pooch_age():
    fake_pooch = FakePooch(age=5, health_loss_age=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_age

        result = await modify_pooch_age(1, 3)
    assert result.age == 8


async def test_modify_pooch_age_clamps_to_zero():
    fake_pooch = FakePooch(age=2, health_loss_age=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_age

        result = await modify_pooch_age(1, -10)
    assert result.age == 0


async def test_modify_pooch_age_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_age

        result = await modify_pooch_age(999, 1)
    assert result is None


async def test_set_pooch_age():
    fake_pooch = FakePooch(age=5, health_loss_age=0)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_age

        result = await set_pooch_age(1, 10)
    assert result.age == 10


async def test_set_pooch_age_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_age

        result = await set_pooch_age(999, 5)
    assert result is None


async def test_set_pooch_base_health():
    fake_pooch = FakePooch(base_health=10)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_base_health

        result = await set_pooch_base_health(1, 20)
    assert result.base_health == 20


async def test_set_pooch_base_health_clamps_to_zero():
    fake_pooch = FakePooch(base_health=10)
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_base_health

        result = await set_pooch_base_health(1, -5)
    assert result.base_health == 0


async def test_set_pooch_base_health_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_base_health

        result = await set_pooch_base_health(999, 10)
    assert result is None


# ---------------------------------------------------------------------------
# update_owner_discord_name
# ---------------------------------------------------------------------------


async def test_update_owner_discord_name():
    fake_owner = FakeOwner()
    fake_owner.discord_name = "OldName"
    scope_cls, _ = _mock_session_scope(owner=fake_owner)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import update_owner_discord_name

        result = await update_owner_discord_name(1, "NewName")
    assert result.discord_name == "NewName"


async def test_update_owner_discord_name_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import update_owner_discord_name

        result = await update_owner_discord_name(999, "NewName")
    assert result is None


# ---------------------------------------------------------------------------
# set_owner_dollars / set_owner_bloodskulls
# ---------------------------------------------------------------------------


async def test_set_owner_dollars():
    fake_owner = FakeOwner(dollars=100)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_dollars

        result = await set_owner_dollars(1, 500)
    assert result.dollars == 500


async def test_set_owner_dollars_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_dollars

        result = await set_owner_dollars(999, 100)
    assert result is None


async def test_set_owner_bloodskulls():
    fake_owner = FakeOwner(bloodskulls=3)
    scope_cls, _ = _mock_session_scope(owner=fake_owner)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_bloodskulls

        result = await set_owner_bloodskulls(1, 10)
    assert result.bloodskulls == 10


async def test_set_owner_bloodskulls_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_bloodskulls

        result = await set_owner_bloodskulls(999, 5)
    assert result is None


# ---------------------------------------------------------------------------
# rename_kennel / rename_pooch returns None when missing
# ---------------------------------------------------------------------------


async def test_rename_kennel_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(kennel=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import rename_kennel

        result = await rename_kennel(999, "NewName")
    assert result is None


async def test_rename_pooch_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import rename_pooch

        result = await rename_pooch(999, "NewName")
    assert result is None


# ---------------------------------------------------------------------------
# reset_begged_today
# ---------------------------------------------------------------------------


async def test_reset_begged_today():
    owners = [FakeOwner(begged_today=True), FakeOwner(begged_today=True)]
    mock_session = AsyncMock()
    mock_response = MagicMock()
    mock_response.scalars.return_value.all.return_value = owners
    mock_session.execute = AsyncMock(return_value=mock_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_begged_today

        count = await reset_begged_today()

    assert count == 2
    assert all(o.begged_today is False for o in owners)


# ---------------------------------------------------------------------------
# reset_visited_park_today
# ---------------------------------------------------------------------------


async def test_reset_visited_park_today():
    owners = [FakeOwner(), FakeOwner()]
    for o in owners:
        o.visited_park_today = True
    mock_session = AsyncMock()
    mock_response = MagicMock()
    mock_response.scalars.return_value.all.return_value = owners
    mock_session.execute = AsyncMock(return_value=mock_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_visited_park_today

        count = await reset_visited_park_today()

    assert count == 2
    assert all(o.visited_park_today is False for o in owners)


# ---------------------------------------------------------------------------
# set_owner_visited_park_today
# ---------------------------------------------------------------------------


async def test_set_owner_visited_park_today():
    fake_owner = FakeOwner()
    fake_owner.visited_park_today = False
    scope_cls, _ = _mock_session_scope(owner=fake_owner)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_visited_park_today

        result = await set_owner_visited_park_today(1, True)
    assert result.visited_park_today is True


async def test_set_owner_visited_park_today_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_visited_park_today

        result = await set_owner_visited_park_today(999)
    assert result is None


# ---------------------------------------------------------------------------
# set_owner_begged_today returns None when missing
# ---------------------------------------------------------------------------


async def test_set_owner_begged_today_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_owner_begged_today

        result = await set_owner_begged_today(999, True)
    assert result is None


# ---------------------------------------------------------------------------
# set_kennel_pooch_limit
# ---------------------------------------------------------------------------


async def test_set_kennel_pooch_limit():
    fake_kennel = FakeKennel(pooch_limit=5)
    scope_cls, _ = _mock_session_scope(kennel=fake_kennel)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_kennel_pooch_limit

        result = await set_kennel_pooch_limit(1, 20)
    assert result.pooch_limit == 20


async def test_set_kennel_pooch_limit_clamps_to_one():
    fake_kennel = FakeKennel(pooch_limit=5)
    scope_cls, _ = _mock_session_scope(kennel=fake_kennel)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_kennel_pooch_limit

        result = await set_kennel_pooch_limit(1, 0)
    assert result.pooch_limit == 1


async def test_set_kennel_pooch_limit_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(kennel=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_kennel_pooch_limit

        result = await set_kennel_pooch_limit(999, 10)
    assert result is None


# ---------------------------------------------------------------------------
# set_pooch_virgin
# ---------------------------------------------------------------------------


async def test_set_pooch_virgin():
    fake_pooch = FakePooch()
    fake_pooch.virgin = True
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_virgin

        result = await set_pooch_virgin(1, False)
    assert result.virgin is False


async def test_set_pooch_virgin_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_virgin

        result = await set_pooch_virgin(999)
    assert result is None


# ---------------------------------------------------------------------------
# transfer_pooch_to_owner / transfer_pooch_to_vendor
# ---------------------------------------------------------------------------


async def test_transfer_pooch_to_owner():
    fake_pooch = FakePooch()
    fake_pooch.owner_discord_id = 1
    fake_pooch.vendor_id = 5
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import transfer_pooch_to_owner

        result = await transfer_pooch_to_owner(1, 99)
    assert result.owner_discord_id == 99
    assert result.vendor_id is None


async def test_transfer_pooch_to_owner_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import transfer_pooch_to_owner

        result = await transfer_pooch_to_owner(999, 1)
    assert result is None


async def test_transfer_pooch_to_vendor():
    fake_pooch = FakePooch()
    fake_pooch.vendor_id = None
    fake_pooch.owner_discord_id = 100
    scope_cls, _ = _mock_session_scope(pooch=fake_pooch)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import transfer_pooch_to_vendor

        result = await transfer_pooch_to_vendor(1, 7)
    assert result.vendor_id == 7
    assert result.owner_discord_id is None


async def test_transfer_pooch_to_vendor_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import transfer_pooch_to_vendor

        result = await transfer_pooch_to_vendor(999, 1)
    assert result is None


# ---------------------------------------------------------------------------
# give_bloodskulls_to_owner returns None when missing
# ---------------------------------------------------------------------------


async def test_give_bloodskulls_to_owner_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_bloodskulls_to_owner

        result = await give_bloodskulls_to_owner(999, 3)
    assert result is None


# ---------------------------------------------------------------------------
# give_bones_to_owner returns None when missing
# ---------------------------------------------------------------------------


async def test_give_bones_to_owner_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(owner=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import give_bones_to_owner

        result = await give_bones_to_owner(999, 10)
    assert result is None


# ---------------------------------------------------------------------------
# tick_hourly_breeding_cooldowns
# ---------------------------------------------------------------------------


async def test_tick_hourly_breeding_cooldowns_decrements_when_chance_hits():
    fake_pooch = FakePooch(breeding_cooldown=3, fertility=100)

    mock_session = AsyncMock()

    # All-pooches query
    all_pooches_response = MagicMock()
    all_pooches_response.scalars.return_value.all.return_value = [fake_pooch]

    # Mutations query (no mutations)
    mutation_response = MagicMock()
    mutation_response.scalars.return_value.all.return_value = []

    # Breeds query (no breeds)
    breed_response = MagicMock()
    breed_response.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[all_pooches_response, mutation_response, breed_response])

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    # fertility=100, divisor=1 → chance=100 → always decrements
    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import tick_hourly_breeding_cooldowns

        count = await tick_hourly_breeding_cooldowns(1.0, rng_seed=42)

    assert count == 1
    assert fake_pooch.breeding_cooldown == 2


async def test_tick_hourly_breeding_cooldowns_no_pooches():
    mock_session = AsyncMock()
    all_pooches_response = MagicMock()
    all_pooches_response.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=all_pooches_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import tick_hourly_breeding_cooldowns

        count = await tick_hourly_breeding_cooldowns(10.0)

    assert count == 0


# ---------------------------------------------------------------------------
# None branches for modify/set stat functions not yet tested
# ---------------------------------------------------------------------------


async def test_modify_pooch_cuteness_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_cuteness

        assert await modify_pooch_cuteness(999, 5) is None


async def test_set_pooch_cuteness_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_cuteness

        assert await set_pooch_cuteness(999, 5) is None


async def test_modify_pooch_fluffiness_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_fluffiness

        assert await modify_pooch_fluffiness(999, 5) is None


async def test_set_pooch_fluffiness_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_fluffiness

        assert await set_pooch_fluffiness(999, 5) is None


async def test_modify_pooch_intelligence_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_intelligence

        assert await modify_pooch_intelligence(999, 5) is None


async def test_set_pooch_intelligence_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_intelligence

        assert await set_pooch_intelligence(999, 5) is None


async def test_modify_pooch_dexterity_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_dexterity

        assert await modify_pooch_dexterity(999, 5) is None


async def test_set_pooch_dexterity_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_dexterity

        assert await set_pooch_dexterity(999, 5) is None


async def test_modify_pooch_fertility_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_fertility

        assert await modify_pooch_fertility(999, 5) is None


async def test_set_pooch_fertility_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_fertility

        assert await set_pooch_fertility(999, 5) is None


async def test_modify_pooch_aggressiveness_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_aggressiveness

        assert await modify_pooch_aggressiveness(999, 5) is None


async def test_set_pooch_aggressiveness_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_aggressiveness

        assert await set_pooch_aggressiveness(999, 5) is None


async def test_modify_pooch_constitution_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_constitution

        assert await modify_pooch_constitution(999, 5) is None


async def test_set_pooch_constitution_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_constitution

        assert await set_pooch_constitution(999, 5) is None


async def test_modify_pooch_breeding_cooldown_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import modify_pooch_breeding_cooldown

        assert await modify_pooch_breeding_cooldown(999, 3) is None


async def test_set_pooch_alive_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_alive

        assert await set_pooch_alive(999) is None


async def test_set_pooch_breeding_cooldown_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_pooch_breeding_cooldown

        assert await set_pooch_breeding_cooldown(999, 5) is None


async def test_reset_pooch_breeding_cooldown_returns_none_when_missing():
    mock_session = AsyncMock()
    pooch_response = MagicMock()
    pooch_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=pooch_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import reset_pooch_breeding_cooldown

        result = await reset_pooch_breeding_cooldown(999)
    assert result is None


# ---------------------------------------------------------------------------
# update_active_event_result / update_active_event_context
# ---------------------------------------------------------------------------


async def test_update_active_event_result():
    fake_event = SimpleNamespace(id=1, result_summary={})
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = fake_event
    mock_session.execute = AsyncMock(return_value=execute_result)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import update_active_event_result

        result = await update_active_event_result(1, {"coins": 50})
    assert result is not None


async def test_update_active_event_result_returns_none_when_missing():
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=execute_result)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import update_active_event_result

        result = await update_active_event_result(999, {})
    assert result is None


async def test_update_active_event_context():
    fake_event = SimpleNamespace(id=1, context={})
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = fake_event
    mock_session.execute = AsyncMock(return_value=execute_result)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import update_active_event_context

        result = await update_active_event_context(1, {"key": "value"})
    assert result is not None


async def test_update_active_event_context_returns_none_when_missing():
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=execute_result)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.update.session_scope", return_value=_FakeScope()):
        from src.database.update import update_active_event_context

        result = await update_active_event_context(999, {})
    assert result is None


# ---------------------------------------------------------------------------
# set_server_event_occurrence_message_discord_id / resolve_server_event_occurrence
# ---------------------------------------------------------------------------


async def test_set_server_event_occurrence_message_discord_id():
    fake_occ = SimpleNamespace(id=1, message_discord_id=None)
    scope_cls, _ = _mock_session_scope(pooch=fake_occ)  # reuse helper; fake_occ is the "entity"
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_server_event_occurrence_message_discord_id

        result = await set_server_event_occurrence_message_discord_id(1, 12345)
    assert result.message_discord_id == 12345


async def test_set_server_event_occurrence_message_discord_id_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import set_server_event_occurrence_message_discord_id

        result = await set_server_event_occurrence_message_discord_id(999, 12345)
    assert result is None


async def test_resolve_server_event_occurrence():
    fake_occ = SimpleNamespace(id=1, result_summary=None, resolved_at=None, archived=False)
    scope_cls, _ = _mock_session_scope(pooch=fake_occ)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import resolve_server_event_occurrence

        result = await resolve_server_event_occurrence(1, {"summary": "done"})
    assert result.archived is True
    assert result.result_summary == {"summary": "done"}


async def test_resolve_server_event_occurrence_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import resolve_server_event_occurrence

        result = await resolve_server_event_occurrence(999)
    assert result is None


# ---------------------------------------------------------------------------
# finalize_server_event_participation
# ---------------------------------------------------------------------------


async def test_finalize_server_event_participation():
    fake_part = SimpleNamespace(id=1, resolution_result=None, score=None, rank=None)
    scope_cls, _ = _mock_session_scope(pooch=fake_part)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import finalize_server_event_participation

        result = await finalize_server_event_participation(1, {"result": "win"}, score=10.0, rank=1)
    assert result.score == 10.0
    assert result.rank == 1


async def test_finalize_server_event_participation_returns_none_when_missing():
    scope_cls, _ = _mock_session_scope(pooch=None)
    with patch("src.database.update.session_scope", return_value=scope_cls()):
        from src.database.update import finalize_server_event_participation

        result = await finalize_server_event_participation(999)
    assert result is None
