"""Root conftest.py — shared fixtures and pytest configuration."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Deterministic RNG
# ---------------------------------------------------------------------------


@pytest.fixture
def rng():
    """Seeded Random instance for deterministic tests."""
    return random.Random(42)


@pytest.fixture
def rng_seed():
    """Fixed seed value for tests that pass seeds to game functions."""
    return 42


# ---------------------------------------------------------------------------
# Game model factories — lightweight SimpleNamespace stubs
# ---------------------------------------------------------------------------


def make_pooch(
    pooch_id=1,
    name="Fido",
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
    owner_discord_id=None,
    vendor_id=None,
    size=10,
    health=10,
    created_at=None,
    mood=None,
    **overrides,
):
    attrs = dict(
        id=pooch_id,
        name=name,
        age=age,
        sex=sex,
        base_health=base_health,
        health_loss_age=health_loss_age,
        strength=strength,
        cuteness=cuteness,
        fluffiness=fluffiness,
        intelligence=intelligence,
        dexterity=dexterity,
        fertility=fertility,
        aggressiveness=aggressiveness,
        constitution=constitution,
        breeding_cooldown=breeding_cooldown,
        alive=alive,
        virgin=virgin,
        owner_discord_id=owner_discord_id,
        vendor_id=vendor_id,
        size=size,
        health=health,
        created_at=created_at,
        mood=mood,
        breeds=[],
        mutations=[],
        parameters={},
    )
    attrs.update(overrides)
    return SimpleNamespace(**attrs)


def make_kennel(kennel_id=1, name="Test Kennel", pooch_limit=10, owner_discord_id=100):
    return SimpleNamespace(id=kennel_id, name=name, pooch_limit=pooch_limit, owner_discord_id=owner_discord_id)


def make_owner(
    discord_id=100,
    discord_name="TestOwner",
    dollars=100,
    bloodskulls=0,
    bones=0,
    begged_today=False,
    visited_park_today=False,
):
    return SimpleNamespace(
        discord_id=discord_id,
        discord_name=discord_name,
        dollars=dollars,
        bloodskulls=bloodskulls,
        bones=bones,
        begged_today=begged_today,
        visited_park_today=visited_park_today,
    )


def make_server(discord_id=200, event_channel_discord_id=None):
    return SimpleNamespace(discord_id=discord_id, event_channel_discord_id=event_channel_discord_id)


def make_vendor(
    vendor_id=1,
    server_discord_id=200,
    name="Test Vendor",
    price_markup=1.0,
    desired_mutation_id_1=None,
    desired_mutation_id_2=None,
    desired_mutation_id_3=None,
):
    return SimpleNamespace(
        id=vendor_id,
        server_discord_id=server_discord_id,
        name=name,
        price_markup=price_markup,
        desired_mutation_id_1=desired_mutation_id_1,
        desired_mutation_id_2=desired_mutation_id_2,
        desired_mutation_id_3=desired_mutation_id_3,
    )


def make_breed(
    breed_id=1, name="TestBreed", category="test", rarity="common", min_size=8, max_size=12, parameters=None
):
    return SimpleNamespace(
        id=breed_id,
        name=name,
        alt_name=None,
        category=category,
        description="A test breed",
        rarity=rarity,
        min_size=min_size,
        max_size=max_size,
        parameters=parameters or {},
    )


def make_mutation(
    mutation_id=1,
    name="TestMutation",
    category="test",
    heritability=0.5,
    health_impact="neutral",
    rarity="common",
    parameters=None,
):
    return SimpleNamespace(
        id=mutation_id,
        name=name,
        alt_name=None,
        category=category,
        description="A test mutation",
        heritability=heritability,
        health_impact=health_impact,
        rarity=rarity,
        affects_males=True,
        affects_females=True,
        parameters=parameters or {},
    )


def make_action(action_type, target_type, parameters=None, repeat=1):
    """Build a minimal EventAction stub."""
    action = MagicMock()
    action.action_type = action_type
    action.target_type = target_type
    action.parameters = parameters or {}
    action.repeat = repeat
    return action


def make_outcome(chance=None, label="outcome", description="desc", message="msg", actions=None, stat_weights=None):
    """Build a minimal EventOutcome stub."""
    o = MagicMock()
    o.chance = chance
    o.label = label
    o.description = description
    o.message = message
    o.actions = actions or []
    o.stat_weights = stat_weights
    return o


def make_option(
    outcomes=None,
    is_default=False,
    is_visible=True,
    actions=None,
    label="Option",
    description="desc",
    min_money=0,
    min_bloodskulls=0,
    filter=None,
):
    """Build a minimal EventOption stub."""
    opt = MagicMock()
    opt.outcomes = outcomes or []
    opt.is_default = is_default
    opt.is_visible = is_visible
    opt.actions = actions or []
    opt.label = label
    opt.description = description
    opt.min_money = min_money
    opt.min_bloodskulls = min_bloodskulls
    opt.filter = filter
    return opt


def make_event_db(
    event_id=1,
    name="TestEvent",
    category="test",
    description="A test event",
    flavor_text="",
    severity="moderate",
    rarity="common",
    requires_response=False,
    response_timeout=24,
    triggered_only=False,
    filter=None,
    actions=None,
    options=None,
):
    """Build a minimal Event DB stub."""
    ev = MagicMock()
    ev.id = event_id
    ev.name = name
    ev.category = category
    ev.description = description
    ev.flavor_text = flavor_text
    ev.severity = severity
    ev.rarity = rarity
    ev.requires_response = requires_response
    ev.response_timeout = response_timeout
    ev.triggered_only = triggered_only
    ev.filter = filter
    ev.actions = actions or []
    ev.options = options or []
    return ev


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Async context manager mock that yields a MagicMock session."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session
