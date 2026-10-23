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
        from src.database import create_owner

        result = await create_owner(12345)

    assert result.discord_id == 12345
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


async def test_create_server_adds_server_to_session():
    """
    Test create server adds server to session.

    Returns
    -------
    Any
        The result of calling `test_create_server_adds_server_to_session`.
    """

    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_server

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
        from src.database import create_kennel

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
        from src.database import create_kennel

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
        from src.database import create_kennel

        result = await create_kennel(123, name="My Kennel", pooch_limit=20, food_stock=150)

    assert result.name == "My Kennel"
    assert result.pooch_limit == 20
    assert result.food_stock == 150


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
        from src.database import create_pooch

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
        from src.database import create_pooch

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
    """
    Test add owner to server.

    Returns
    -------
    Any
        The result of calling `test_add_owner_to_server`.
    """

    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import add_owner_to_server

        result = await add_owner_to_server(server_discord_id=111, owner_discord_id=222)

    assert result.server_discord_id == 111
    assert result.owner_discord_id == 222
    mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# add_pooch_to_kennel
# ---------------------------------------------------------------------------


async def test_add_pooch_to_kennel():
    """
    Test add pooch to kennel.

    Returns
    -------
    Any
        The result of calling `test_add_pooch_to_kennel`.
    """

    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import add_pooch_to_kennel

        result = await add_pooch_to_kennel(kennel_id=1, pooch_id=2)

    assert result.kennel_id == 1
    assert result.pooch_id == 2


# ---------------------------------------------------------------------------
# create_pooch_pregnancy
# ---------------------------------------------------------------------------


async def test_create_pooch_pregnancy():
    """
    Test create pooch pregnancy.

    Returns
    -------
    Any
        The result of calling `test_create_pooch_pregnancy`.
    """

    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_pooch_pregnancy

        result = await create_pooch_pregnancy(mother_id=10, fetus_id=20)

    assert result.mother_id == 10
    assert result.fetus_id == 20


# ---------------------------------------------------------------------------
# bury_pooch
# ---------------------------------------------------------------------------


async def test_bury_pooch_returns_none_when_owner_missing():
    """
    Test bury pooch returns none when owner missing.

    Returns
    -------
    Any
        The result of calling `test_bury_pooch_returns_none_when_owner_missing`.
    """

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
    ):
        from src.database import bury_pooch

        result = await bury_pooch(999, 1)

    assert result is None


async def test_bury_pooch_returns_none_when_pooch_missing():
    """
    Test bury pooch returns none when pooch missing.

    Returns
    -------
    Any
        The result of calling `test_bury_pooch_returns_none_when_pooch_missing`.
    """

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=SimpleNamespace(discord_id=1))),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)),
    ):
        from src.database import bury_pooch

        result = await bury_pooch(1, 999)

    assert result is None


async def test_bury_pooch_success():
    """
    Test bury pooch success.

    Returns
    -------
    Any
        The result of calling `test_bury_pooch_success`.
    """

    fake_owner = SimpleNamespace(discord_id=1)
    fake_pooch = SimpleNamespace(id=10)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_owner_by_discord_id", new=AsyncMock(return_value=fake_owner)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=fake_pooch)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database import bury_pooch

        result = await bury_pooch(1, 10)

    assert result.owner_discord_id == 1
    assert result.pooch_id == 10


# ---------------------------------------------------------------------------
# add_pooch_breeds
# ---------------------------------------------------------------------------


async def test_add_pooch_breeds_ignores_non_positive_weights():
    """
    Test add pooch breeds ignores non positive weights.

    Returns
    -------
    Any
        The result of calling `test_add_pooch_breeds_ignores_non_positive_weights`.
    """

    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import add_pooch_breeds

        result = await add_pooch_breeds(1, {10: 2, 11: 0, 12: -1})

    # Only the breed with weight=2 should be added
    assert len(result) == 1
    assert result[0].breed_id == 10
    assert result[0].weight == 2


async def test_add_pooch_breeds_empty():
    """
    Test add pooch breeds empty.

    Returns
    -------
    Any
        The result of calling `test_add_pooch_breeds_empty`.
    """

    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import add_pooch_breeds

        result = await add_pooch_breeds(1, {})

    assert result == []


# ---------------------------------------------------------------------------
# add_pooch_to_vendor_stock
# ---------------------------------------------------------------------------


async def test_add_pooch_to_vendor_stock_returns_none_when_vendor_missing():
    """
    Test add pooch to vendor stock returns none when vendor missing.

    Returns
    -------
    Any
        The result of calling `test_add_pooch_to_vendor_stock_returns_none_when_vendor_missing`.
    """

    with (
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=None)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
    ):
        from src.database import add_pooch_to_vendor_stock

        result = await add_pooch_to_vendor_stock(999, 1)

    assert result is None


async def test_add_pooch_to_vendor_stock_returns_none_when_pooch_missing():
    """
    Test add pooch to vendor stock returns none when pooch missing.

    Returns
    -------
    Any
        The result of calling `test_add_pooch_to_vendor_stock_returns_none_when_pooch_missing`.
    """

    with (
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=SimpleNamespace(id=1))),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)),
    ):
        from src.database import add_pooch_to_vendor_stock

        result = await add_pooch_to_vendor_stock(1, 999)

    assert result is None


async def test_add_pooch_to_vendor_stock_success():
    """
    Test add pooch to vendor stock success.

    Returns
    -------
    Any
        The result of calling `test_add_pooch_to_vendor_stock_success`.
    """

    fake_vendor = SimpleNamespace(id=1)
    fake_pooch = SimpleNamespace(id=10)
    scope_cls, mock_session = _mock_session_scope()

    with (
        patch("src.database.set.get_vendor_by_id", new=AsyncMock(return_value=fake_vendor)),
        patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=fake_pooch)),
        patch("src.database.set.session_scope", return_value=scope_cls()),
    ):
        from src.database import add_pooch_to_vendor_stock

        result = await add_pooch_to_vendor_stock(1, 10)

    assert result.vendor_id == 1
    assert result.pooch_id == 10


# ---------------------------------------------------------------------------
# add_breed_to_pooch (with explicit breed_id, skips random path)
# ---------------------------------------------------------------------------


async def test_add_breed_to_pooch_returns_existing_when_already_present():
    """If the breed is already on the pooch (sole breed), return via scalar lookup."""
    existing = SimpleNamespace(pooch_id=1, breed_id=5)

    mock_session = AsyncMock()
    # scalar returns existing relationship (others_total == 0 path)
    mock_session.scalar = AsyncMock(return_value=existing)

    # response.tuples().all() returns [(breed_id=5, weight=4)] — only this breed
    existing_response = MagicMock()
    existing_response.tuples.return_value.all.return_value = [(5, 4)]
    mock_session.execute = AsyncMock(return_value=existing_response)
    mock_session.flush = AsyncMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with patch("src.database.set.session_scope", return_value=_FakeScope()):
        from src.database import add_breed_to_pooch

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
        from src.database import add_breed_to_pooch

        result = await add_breed_to_pooch(pooch_id=1, breed_id=5, weight=1.0)

    assert result.weight == 1
    assert result.pooch_id == 1
    assert result.breed_id == 5


async def test_add_breed_to_pooch_partial_weight():
    """Partial weight should compute a relative weight and add the breed."""
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=None)

    # execute for existing breeds weight query; response.tuples().all() returns [(breed_id, weight), ...]
    weight_response = MagicMock()
    weight_response.tuples.return_value.all.return_value = [(3, 4)]  # one other breed with weight=4
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
        from src.database import add_breed_to_pooch

        result = await add_breed_to_pooch(pooch_id=1, breed_id=5, weight=0.5)

    assert result.pooch_id == 1
    assert result.breed_id == 5
    assert result.weight >= 1


# ---------------------------------------------------------------------------
# add_mutation_to_pooch (with explicit mutation_id)
# ---------------------------------------------------------------------------


async def test_add_mutation_to_pooch_returns_existing_when_already_present():
    """
    Test add mutation to pooch returns existing when already present.

    Returns
    -------
    Any
        The result of calling `test_add_mutation_to_pooch_returns_existing_when_already_present`.
    """

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
        from src.database import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=3)

    assert result is existing


async def test_add_mutation_to_pooch_returns_none_when_mutation_not_found():
    """
    Test add mutation to pooch returns none when mutation not found.

    Returns
    -------
    Any
        The result of calling `test_add_mutation_to_pooch_returns_none_when_mutation_not_found`.
    """

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
        from src.database import add_mutation_to_pooch

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
        from src.database import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=5)

    assert result is None


async def test_add_mutation_to_pooch_success():
    """Compatible mutation should be added and returned."""
    new_mutation = SimpleNamespace(
        id=5, name="Berserker", parameters={"incompatible_mutations": []}, visible=True, invisible_messages=None
    )

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
        from src.database import add_mutation_to_pooch

        result = await add_mutation_to_pooch(pooch_id=1, mutation_id=5)

    assert result is not None
    assert result.pooch_id == 1
    assert result.mutation_id == 5


# ---------------------------------------------------------------------------
# create_active_owner_event
# ---------------------------------------------------------------------------


async def test_create_active_owner_event():
    """
    Test create active owner event.

    Returns
    -------
    Any
        The result of calling `test_create_active_owner_event`.
    """

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
        from src.database import create_active_owner_event

        result = await create_active_owner_event(event_id=1, owner_discord_id=42)

    assert result is not None
    assert result.event_id == 1
    assert result.owner_discord_id == 42


# ---------------------------------------------------------------------------
# damn_pooch
# ---------------------------------------------------------------------------


async def test_damn_pooch_returns_none_when_pooch_missing():
    """
    Test damn pooch returns none when pooch missing.

    Returns
    -------
    Any
        The result of calling `test_damn_pooch_returns_none_when_pooch_missing`.
    """

    with patch("src.database.set.get_pooch_by_id", new=AsyncMock(return_value=None)):
        from src.database import damn_pooch

        result = await damn_pooch(999)
    assert result is None


async def test_damn_pooch_adds_to_hell():
    """
    Test damn pooch adds to hell.

    Returns
    -------
    Any
        The result of calling `test_damn_pooch_adds_to_hell`.
    """

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
        from src.database import damn_pooch

        result = await damn_pooch(10)

    assert result is not None
    assert result.pooch_id == 10


# ---------------------------------------------------------------------------
# revive_pooch
# ---------------------------------------------------------------------------


async def test_revive_pooch_returns_none_when_missing():
    """
    Test revive pooch returns none when missing.

    Returns
    -------
    Any
        The result of calling `test_revive_pooch_returns_none_when_missing`.
    """

    scope_cls, mock_session = _mock_session_scope()
    mock_response = MagicMock()
    mock_response.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_response)
    mock_session.get = AsyncMock(return_value=None)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import revive_pooch

        result = await revive_pooch(999)
    assert result is None


async def test_revive_pooch_sets_alive():
    """
    Test revive pooch sets alive.

    Returns
    -------
    Any
        The result of calling `test_revive_pooch_sets_alive`.
    """

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
        from src.database import revive_pooch

        result = await revive_pooch(5)
    assert result.alive is True


# ---------------------------------------------------------------------------
# set_pooch_parentage
# ---------------------------------------------------------------------------


async def test_set_pooch_parentage():
    """
    Test set pooch parentage.

    Returns
    -------
    Any
        The result of calling `test_set_pooch_parentage`.
    """

    scope_cls, mock_session = _mock_session_scope()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import set_pooch_parentage

        result = await set_pooch_parentage(child_id=3, father_id=1, mother_id=2)

    assert result.child_id == 3
    assert result.father_id == 1
    assert result.mother_id == 2


# ---------------------------------------------------------------------------
# create_server_event_occurrence
# ---------------------------------------------------------------------------


async def test_create_server_event_occurrence():
    """
    Test create server event occurrence.

    Returns
    -------
    Any
        The result of calling `test_create_server_event_occurrence`.
    """

    from datetime import datetime, timezone

    scope_cls, mock_session = _mock_session_scope()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: None)

    expires = datetime.now(timezone.utc)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_server_event_occurrence

        result = await create_server_event_occurrence(200, 10, {}, expires)

    assert result.server_discord_id == 200
    assert result.server_event_id == 10


# ---------------------------------------------------------------------------
# create_server_event_participation
# ---------------------------------------------------------------------------


async def test_create_server_event_participation():
    """
    Test create server event participation.

    Returns
    -------
    Any
        The result of calling `test_create_server_event_participation`.
    """

    scope_cls, mock_session = _mock_session_scope()

    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: None)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_server_event_participation

        result = await create_server_event_participation(5, 100, {}, {"answer": "yes"}, {"coins": 10})

    assert result.occurrence_id == 5
    assert result.owner_discord_id == 100


# ---------------------------------------------------------------------------
# create_auction_sale_listing
# ---------------------------------------------------------------------------


async def test_create_auction_sale_listing_adds_listing():
    """create_auction_sale_listing should create a listing with the correct fields."""
    from datetime import datetime, timezone

    scope_cls, mock_session = _mock_session_scope()
    expires = datetime(2030, 1, 1, tzinfo=timezone.utc)

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_auction_sale_listing

        result = await create_auction_sale_listing(
            pooch_id=10,
            seller_discord_id=42,
            server_discord_id=5,
            minimum_bid=100,
            expires_at=expires,
        )

    assert result.pooch_id == 10
    assert result.seller_discord_id == 42
    assert result.server_discord_id == 5
    assert result.minimum_bid == 100
    assert result.expires_at == expires
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


async def test_create_auction_sale_listing_no_expiry():
    """create_auction_sale_listing should work with expires_at=None."""
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_auction_sale_listing

        result = await create_auction_sale_listing(
            pooch_id=1,
            seller_discord_id=10,
            server_discord_id=2,
            minimum_bid=0,
        )

    assert result.expires_at is None
    mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# create_auction_bid
# ---------------------------------------------------------------------------


async def test_create_auction_bid_adds_bid():
    """create_auction_bid should insert a bid row with the correct fields."""
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_auction_bid

        result = await create_auction_bid(listing_id=5, bidder_discord_id=99, amount=250)

    assert result.listing_id == 5
    assert result.bidder_discord_id == 99
    assert result.amount == 250
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_auction_bounty_listing
# ---------------------------------------------------------------------------


async def test_create_auction_bounty_listing_adds_listing():
    """create_auction_bounty_listing should create a bounty with the correct fields."""
    criteria = [{"type": "sex", "value": "female", "dollar_value": 50}]
    scope_cls, mock_session = _mock_session_scope()

    with patch("src.database.set.session_scope", return_value=scope_cls()):
        from src.database import create_auction_bounty_listing

        result = await create_auction_bounty_listing(
            buyer_discord_id=77,
            server_discord_id=3,
            title="Wanted: Female Dog",
            escrow_amount=500,
            criteria=criteria,
        )

    assert result.buyer_discord_id == 77
    assert result.server_discord_id == 3
    assert result.title == "Wanted: Female Dog"
    assert result.escrow_amount == 500
    assert result.criteria == criteria
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()
