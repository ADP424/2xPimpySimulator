import random
from typing import Optional, TypeVar

T = TypeVar("T")


def weighted_choice(rng: random.Random, items: list[tuple[T, int]]) -> Optional[T]:
    if len(items) == 0:
        return None

    total = sum(weight for _, weight in items)
    roll = rng.uniform(0, total)

    accumulated = 0
    for item, weight in items:
        accumulated += weight
        if roll <= accumulated:
            return item
