"""Tests for src/database/set.py (creation functions).

Functions under test open their own session_scope, so we mock it.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_scope():
    """Return a mock session that tracks .add() and .flush() calls."""
    mock_session = AsyncMock()
    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.scalar = AsyncMock()
    mock_session._added = added_objects

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _FakeScope, mock_session


# ---------------------------------------------------------------------------
# create_owner
# ---------------------------------------------------------------------------


async def test_create_owner_adds_owner_to_session():
    """create_owner should add an Owner with the given discord_id to the session."""
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_owner

        result = await create_owner(12345)

    assert result.discord_id == 12345
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


async def test_create_server_adds_server_to_session():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_server

        result = await create_server(67890)

    assert result.discord_id == 67890
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_kennel
# ---------------------------------------------------------------------------


async def test_create_kennel_returns_none_when_owner_missing():
    """create_kennel should return None when the owner doesn't exist."""
    with patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)):
        from src.database.set import create_kennel

        result = await create_kennel(999)

    assert result is None


async def test_create_kennel_creates_with_defaults():
    """create_kennel should create a kennel with default name and pooch_limit."""
    fake_owner = SimpleNamespace(discord_id=123)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_kennel

        result = await create_kennel(123)

    assert result is not None
    assert result.owner_discord_id == 123
    assert result.name == "Kennel"
    mock_session.flush.assert_awaited_once()


async def test_create_kennel_with_custom_name_and_limit():
    """create_kennel should respect custom name and pooch_limit."""
    fake_owner = SimpleNamespace(discord_id=123)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_kennel

        result = await create_kennel(123, name="My Kennel", pooch_limit=20)

    assert result.name == "My Kennel"
    assert result.pooch_limit == 20


# ---------------------------------------------------------------------------
# create_pooch
# ---------------------------------------------------------------------------


async def test_create_pooch_with_explicit_values():
    """create_pooch should set all explicit stat values on the created pooch."""
    scope_cls, mock_session = _mock_session_scope()
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.scalar = AsyncMock(return_value=None)

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_pooch

        result = await create_pooch(
            name="TestDog",
            sex="male",
            age=3,
            base_health=15,
            strength=12,
            cuteness=8,
            fluffiness=7,
            intelligence=11,
            dexterity=9,
            fertility=10,
            aggressiveness=5,
            size=10,
        )

    assert result.name == "TestDog"
    assert result.sex == "male"
    assert result.age == 3
    assert result.base_health == 15
    assert result.strength == 12
    assert result.cuteness == 8
    assert result.fluffiness == 7
    assert result.intelligence == 11
    assert result.dexterity == 9
    assert result.fertility == 10
    assert result.aggressiveness == 5
    assert result.size == 10
    assert result.alive is True
    assert result.virgin is True


async def test_create_pooch_vendor_clears_when_owner_given():
    """If both owner and vendor are given, vendor should be cleared."""
    fake_owner = SimpleNamespace(discord_id=1)
    fake_vendor = SimpleNamespace(id=2)
    scope_cls, mock_session = _mock_session_scope()
    mock_session.scalar = AsyncMock(return_value=None)
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=fake_vendor)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import create_pooch

        result = await create_pooch(
            owner_discord_id=1,
            vendor_id=2,
            name="Fido",
            sex="female",
            size=10,
        )

    assert result.owner_discord_id == 1
    assert result.vendor_id is None


# ---------------------------------------------------------------------------
# add_owner_to_server
# ---------------------------------------------------------------------------


async def test_add_owner_to_server():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import add_owner_to_server

        result = await add_owner_to_server(server_discord_id=111, owner_discord_id=222)

    assert result.server_discord_id == 111
    assert result.owner_discord_id == 222
    mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# add_pooch_to_kennel
# ---------------------------------------------------------------------------


async def test_add_pooch_to_kennel():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import add_pooch_to_kennel

        result = await add_pooch_to_kennel(kennel_id=1, pooch_id=2)

    assert result.kennel_id == 1
    assert result.pooch_id == 2


# ---------------------------------------------------------------------------
# create_pooch_pregnancy
# ---------------------------------------------------------------------------


async def test_create_pooch_pregnancy():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_pooch_pregnancy

        result = await create_pooch_pregnancy(mother_id=10, fetus_id=20)

    assert result.mother_id == 10
    assert result.fetus_id == 20


# ---------------------------------------------------------------------------
# bury_pooch
# ---------------------------------------------------------------------------


async def test_bury_pooch_returns_none_when_owner_missing():
    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
    ):
        from src.database.set import bury_pooch

        result = await bury_pooch(999, 1)

    assert result is None


async def test_bury_pooch_returns_none_when_pooch_missing():
    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=SimpleNamespace(discord_id=1))),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)),
    ):
        from src.database.set import bury_pooch

        result = await bury_pooch(1, 999)

    assert result is None


async def test_bury_pooch_success():
    fake_owner = SimpleNamespace(discord_id=1)
    fake_pooch = SimpleNamespace(id=10)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=fake_pooch)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import bury_pooch

        result = await bury_pooch(1, 10)

    assert result.owner_discord_id == 1
    assert result.pooch_id == 10


# ---------------------------------------------------------------------------
# add_pooch_breeds
# ---------------------------------------------------------------------------


async def test_add_pooch_breeds_ignores_non_positive_weights():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import add_pooch_breeds

        result = await add_pooch_breeds(1, {10: 2, 11: 0, 12: -1})

    # Only the breed with weight=2 should be added
    assert len(result) == 1
    assert result[0].breed_id == 10
    assert result[0].weight == 2


async def test_add_pooch_breeds_empty():
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import add_pooch_breeds

        result = await add_pooch_breeds(1, {})

    assert result == []


# ---------------------------------------------------------------------------
# add_pooch_to_vendor_stock
# ---------------------------------------------------------------------------


async def test_add_pooch_to_vendor_stock_returns_none_when_vendor_missing():
    with (
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
    ):
        from src.database.set import add_pooch_to_vendor_stock

        result = await add_pooch_to_vendor_stock(999, 1)

    assert result is None


async def test_add_pooch_to_vendor_stock_returns_none_when_pooch_missing():
    with (
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)),
    ):
        from src.database.set import add_pooch_to_vendor_stock

        result = await add_pooch_to_vendor_stock(1, 999)

    assert result is None


async def test_add_pooch_to_vendor_stock_success():
    fake_vendor = SimpleNamespace(id=1)
    fake_pooch = SimpleNamespace(id=10)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=fake_vendor)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=fake_pooch)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import add_pooch_to_vendor_stock

        result = await add_pooch_to_vendor_stock(1, 10)

    assert result.vendor_id == 1
    assert result.pooch_id == 10


# ---------------------------------------------------------------------------
# add_breed_to_pooch (with explicit breed_id, skips random path)
# ---------------------------------------------------------------------------


async def test_add_breed_to_pooch_returns_existing_when_already_present():
    """If the breed is already on the pooch, return the existing PoochBreed."""
    existing = SimpleNamespace(pooch_id=1, breed_id=5)

    mock_session = AsyncMock()
    # execute for breed_query not called since breed_id is given
    # scalar returns existing relationship
    mock_session.scalar = AsyncMock(return_value=existing)
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_breed_to_pooch

        result = await add_breed_to_pooch(pooch_id=1, breed_id=5)

    assert result is existing


async def test_add_breed_to_pooch_full_weight_replaces_existing():
    """Weight >= 1.0 should delete existing breeds and add the new one as weight=1."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=None)  # no existing PoochBreed
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_breed_to_pooch

        result = await add_breed_to_pooch(pooch_id=1, breed_id=5, weight=1.0)

    assert result.weight == 1
    assert result.pooch_id == 1
    assert result.breed_id == 5


async def test_add_breed_to_pooch_partial_weight():
    """Partial weight should compute a relative weight and add the breed."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=None)

    # execute for existing breeds weight query
    weight_response = MagicMock()
    weight_response.scalars.return_value.all.return_value = [4]  # total existing weight = 4
    mock_session.execute = AsyncMock(return_value=weight_response)
    mock_session.flush = AsyncMock()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    # weight=0.5 means new breed = 50% of total. relative = 0.5/0.5 * 4 = 4
    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_breed_to_pooch

        result = await add_breed_to_pooch(pooch_id=1, breed_id=5, weight=0.5)

    assert result.pooch_id == 1
    assert result.breed_id == 5
    assert result.weight >= 1


# ---------------------------------------------------------------------------
# add_mutation_to_pooch (with explicit mutation_id)
# ---------------------------------------------------------------------------


async def test_add_mutation_to_pooch_returns_existing_when_already_present():
    existing = SimpleNamespace(pooch_id=1, mutation_id=3)

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=existing)
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=3)

    assert result is existing


async def test_add_mutation_to_pooch_returns_none_when_mutation_not_found():
    mock_session = AsyncMock()
    # First scalar: no existing PoochMutation; second scalar: Mutation not found
    mock_session.scalar = AsyncMock(side_effect=[None, None])

    existing_mutations_response = MagicMock()
    existing_mutations_response.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=existing_mutations_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=99)

    assert result is None


async def test_add_mutation_to_pooch_returns_none_when_incompatible():
    """Mutation that is incompatible with existing ones should return None."""
    new_mutation = SimpleNamespace(id=5, name="Berserker", parameters={"incompatible_mutations": ["Calm"]})
    existing_mutation = SimpleNamespace(id=2, name="Calm", parameters={"incompatible_mutations": []})

    mock_session = AsyncMock()
    # scalar calls: no existing PoochMutation, then the new mutation itself
    mock_session.scalar = AsyncMock(side_effect=[None, new_mutation])

    existing_mutations_response = MagicMock()
    existing_mutations_response.scalars.return_value.all.return_value = [existing_mutation]
    mock_session.execute = AsyncMock(return_value=existing_mutations_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=5)

    assert result is None


async def test_add_mutation_to_pooch_success():
    """Compatible mutation should be added and returned."""
    new_mutation = SimpleNamespace(id=5, name="Berserker", parameters={"incompatible_mutations": []})

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[None, new_mutation])

    existing_mutations_response = MagicMock()
    existing_mutations_response.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=existing_mutations_response)

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=5)

    assert result is not None
    assert result.pooch_id == 1
    assert result.mutation_id == 5


# ---------------------------------------------------------------------------
# create_active_owner_event
# ---------------------------------------------------------------------------


async def test_create_active_owner_event():
    fake_event = SimpleNamespace(id=100, event_id=1, owner_discord_id=42)

    mock_session = AsyncMock()
    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()

    reload_response = MagicMock()
    reload_response.scalar_one_or_none.return_value = fake_event
    mock_session.execute = AsyncMock(return_value=reload_response)

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database.set import create_active_owner_event

        result = await create_active_owner_event(event_id=1, owner_discord_id=42)

    assert result is not None
    assert result.event_id == 1
    assert result.owner_discord_id == 42


# ---------------------------------------------------------------------------
# damn_pooch
# ---------------------------------------------------------------------------


async def test_damn_pooch_returns_none_when_pooch_missing():
    with patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)):
        from src.database.set import damn_pooch

        result = await damn_pooch(999)
    assert result is None


async def test_damn_pooch_adds_to_hell():
    fake_pooch = SimpleNamespace(id=10)
    scope_cls, mock_session = _mock_session_scope()

    # KennelPooch query (no kennel row)
    kennel_execute = MagicMock()
    kennel_execute.scalar_one_or_none.return_value = None
    # GraveyardPooch query (no grave row)
    grave_execute = MagicMock()
    grave_execute.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(side_effect=[kennel_execute, grave_execute])
    # session.get for StrayPooch and HellPooch
    mock_session.get = AsyncMock(return_value=None)
    mock_session.flush = AsyncMock()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    with (
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=fake_pooch)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database.set import damn_pooch

        result = await damn_pooch(10)

    assert result is not None
    assert result.pooch_id == 10


# ---------------------------------------------------------------------------
# revive_pooch
# ---------------------------------------------------------------------------


async def test_revive_pooch_returns_none_when_missing():
    scope_cls, mock_session = _mock_session_scope()
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.get = AsyncMock(return_value=None)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import revive_pooch

        result = await revive_pooch(999)
    assert result is None


async def test_revive_pooch_sets_alive():
    fake_pooch = SimpleNamespace(id=5, alive=False)
    scope_cls, mock_session = _mock_session_scope()

    pooch_response = MagicMock()
    pooch_response.scalar_one_or_none.return_value = fake_pooch
    graveyard_response = MagicMock()
    graveyard_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(side_effect=[pooch_response, graveyard_response])
    mock_session.get = AsyncMock(return_value=None)
    mock_session.flush = AsyncMock()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import revive_pooch

        result = await revive_pooch(5)
    assert result.alive is True


# ---------------------------------------------------------------------------
# set_pooch_parentage
# ---------------------------------------------------------------------------


async def test_set_pooch_parentage():
    scope_cls, mock_session = _mock_session_scope()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import set_pooch_parentage

        result = await set_pooch_parentage(child_id=3, father_id=1, mother_id=2)

    assert result.child_id == 3
    assert result.father_id == 1
    assert result.mother_id == 2


# ---------------------------------------------------------------------------
# create_server_event_occurrence
# ---------------------------------------------------------------------------


async def test_create_server_event_occurrence():
    from datetime import datetime, timezone

    scope_cls, mock_session = _mock_session_scope()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: None)

    expires = datetime.now(timezone.utc)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_server_event_occurrence

        result = await create_server_event_occurrence(200, 10, {}, expires)

    assert result.server_discord_id == 200
    assert result.server_event_id == 10


# ---------------------------------------------------------------------------
# create_server_event_participation
# ---------------------------------------------------------------------------


async def test_create_server_event_participation():
    scope_cls, mock_session = _mock_session_scope()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: None)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database.set import create_server_event_participation

        result = await create_server_event_participation(5, 100, {}, {"answer": "yes"}, {"coins": 10})

    assert result.occurrence_id == 5
    assert result.owner_discord_id == 100
