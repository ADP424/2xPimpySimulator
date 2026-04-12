import random
from collections import defaultdict
from typing import Optional, TypeVar

T = TypeVar("T")

# Rarity weights ordered from most common to most rare
RARITY_WEIGHTS: dict[str, int] = {
    "common": 1000,
    "uncommon": 250,
    "novel": 100,
    "rare": 50,
    "unprecedented": 25,
    "remarkable": 10,
    "extraordinary": 5,
    "unique": 1,
}


def weighted_choice(rng: random.Random, items: list[tuple[T, int]]) -> Optional[T]:
    """
    Weighted choice.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    items: Any
        The `items` value.

    Returns
    -------
    Any
        The result of calling `weighted_choice`.
    """

    if len(items) == 0:
        return None

    total = sum(weight for _, weight in items)
    roll = rng.uniform(0, total)

    accumulated = 0
    for item, weight in items:
        accumulated += weight
        if roll <= accumulated:
            return item


def rarity_choice(rng: random.Random, items: list[tuple[T, str]]) -> Optional[T]:
    """
    Two-step rarity selection: first roll which rarity tier wins (weighted by RARITY_WEIGHTS),
    then pick uniformly at random from all items of that rarity.

    Parameters
    ----------
    rng: random.Random
        The random generator to use.

    items: list[tuple[T, str]]
        A list of (item, rarity_string) pairs.

    Returns
    -------
    T, optional
        A randomly selected item, or None if `items` is empty.
    """

    if not items:
        return None

    # Group items by rarity, keeping only rarities that have at least one item
    buckets: dict[str, list[T]] = defaultdict(list)
    for item, rarity in items:
        buckets[rarity].append(item)

    # Build weighted list of present rarities
    rarity_pool: list[tuple[str, int]] = [
        (rarity, RARITY_WEIGHTS[rarity]) for rarity in buckets if rarity in RARITY_WEIGHTS
    ]
    if not rarity_pool:
        return None

    # Roll which rarity wins
    total = sum(w for _, w in rarity_pool)
    roll = rng.uniform(0, total)
    accumulated = 0
    chosen_rarity = rarity_pool[-1][0]
    for rarity, weight in rarity_pool:
        accumulated += weight
        if roll <= accumulated:
            chosen_rarity = rarity
            break

    return rng.choice(buckets[chosen_rarity])
