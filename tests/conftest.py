"""Shared test fixtures and factory functions for use across all test modules."""

from types import SimpleNamespace
from typing import Any


def make_pooch(
    pooch_id: int = 1,
    name: str = "Buddy",
    age: int = 0,
    sex: str = "male",
    alive: bool = True,
    virgin: bool = True,
    base_health: int = 10,
    health_loss_age: int = 0,
    strength: int = 10,
    cuteness: int = 10,
    fluffiness: int = 10,
    intelligence: int = 10,
    dexterity: int = 10,
    fertility: int = 10,
    aggressiveness: int = 10,
    constitution: int = 10,
    size: int = 10,
    breeding_cooldown: int = 0,
    mood: str | None = None,
    owner_discord_id: int | None = None,
    vendor_id: int | None = None,
    mutations: list | None = None,
    breeds: list | None = None,
    injuries: list | None = None,
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Pooch-like namespace for use in unit tests."""
    return SimpleNamespace(
        id=pooch_id,
        name=name,
        age=age,
        sex=sex,
        alive=alive,
        virgin=virgin,
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
        size=size,
        breeding_cooldown=breeding_cooldown,
        mood=mood,
        owner_discord_id=owner_discord_id,
        vendor_id=vendor_id,
        mutations=mutations if mutations is not None else [],
        breeds=breeds if breeds is not None else [],
        injuries=injuries if injuries is not None else [],
        **kwargs,
    )


def make_breed(
    breed_id: int = 1,
    name: str = "Retriever",
    alt_name: str = "Retriever",
    category: str = "Sporting",
    description: str = "A friendly dog.",
    rarity: str = "common",
    min_size: int = 8,
    max_size: int = 12,
    parameters: dict | None = None,
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Breed-like namespace for use in unit tests."""
    return SimpleNamespace(
        id=breed_id,
        name=name,
        alt_name=alt_name,
        category=category,
        description=description,
        rarity=rarity,
        min_size=min_size,
        max_size=max_size,
        parameters=parameters if parameters is not None else {},
        **kwargs,
    )


def make_mutation(
    mutation_id: int = 1,
    name: str = "Cataracts",
    alt_name: str = "Cataracts",
    category: str = "Vision",
    description: str = "Blurry vision.",
    heritability: float = 0.25,
    health_impact: str = "neutral",
    rarity: str = "common",
    affects_females: bool = True,
    affects_males: bool = True,
    parameters: dict | None = None,
    visible: bool = True,
    invisible_messages: list[str] | None = None,
    reveal_chance: float = 1.0,
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Mutation-like namespace for use in unit tests."""
    return SimpleNamespace(
        id=mutation_id,
        name=name,
        alt_name=alt_name,
        category=category,
        description=description,
        heritability=heritability,
        health_impact=health_impact,
        rarity=rarity,
        affects_females=affects_females,
        affects_males=affects_males,
        parameters=parameters if parameters is not None else {},
        visible=visible,
        invisible_messages=invisible_messages,
        reveal_chance=reveal_chance,
        **kwargs,
    )


def make_owner(
    discord_id: int = 1,
    discord_name: str | None = "TestUser",
    dollars: int = 100,
    bloodskulls: int = 0,
    bones: int = 0,
    begged_today: bool = False,
    visited_park_today: bool = False,
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Owner-like namespace for use in unit tests."""
    return SimpleNamespace(
        discord_id=discord_id,
        discord_name=discord_name,
        dollars=dollars,
        bloodskulls=bloodskulls,
        bones=bones,
        begged_today=begged_today,
        visited_park_today=visited_park_today,
        **kwargs,
    )


def make_kennel(
    kennel_id: int = 1,
    owner_discord_id: int = 1,
    name: str = "My Kennel",
    pooch_limit: int = 10,
    upgrade_tier: int = 0,
    pooches: list | None = None,
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Kennel-like namespace for use in unit tests."""
    return SimpleNamespace(
        id=kennel_id,
        owner_discord_id=owner_discord_id,
        name=name,
        pooch_limit=pooch_limit,
        upgrade_tier=upgrade_tier,
        pooches=pooches if pooches is not None else [],
        **kwargs,
    )


def make_server(
    discord_id: int = 1,
    event_channel_discord_id: int | None = None,
    current_season: str = "spring",
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Server-like namespace for use in unit tests."""
    return SimpleNamespace(
        discord_id=discord_id,
        event_channel_discord_id=event_channel_discord_id,
        current_season=current_season,
        **kwargs,
    )


def make_vendor(
    vendor_id: int = 1,
    server_discord_id: int = 1,
    name: str = "Test Vendor",
    price_markup: float = 1.0,
    **kwargs: Any,
) -> SimpleNamespace:
    """Create a lightweight Vendor-like namespace for use in unit tests."""
    return SimpleNamespace(
        id=vendor_id,
        server_discord_id=server_discord_id,
        name=name,
        price_markup=price_markup,
        **kwargs,
    )
