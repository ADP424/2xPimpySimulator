"""
Rarity-weight sorting helpers.

The game's rarity enum is ordered from most-common to most-rare. When showing
breed/mutation/injury/disease filters in a bot or web dropdown, we want the
most-common (highest weight) entries to appear first so players aren't buried
under novelty.

``weight_for_rarity`` maps a rarity string to a numeric weight (higher = more
common). ``sort_by_rarity_weight`` is the generic sort helper every UI layer
should call.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, TypeVar

# Ordered most-common → most-rare. Index position maps to a numeric weight
# so "common" is highest (8) and "unique" is lowest (1). Matches the RARITY
# postgres enum defined in src/database/models/enums/rarity.py.
_RARITY_ORDER: tuple[str, ...] = (
    "common",
    "uncommon",
    "novel",
    "rare",
    "unprecedented",
    "remarkable",
    "extraordinary",
    "unique",
)

_RARITY_WEIGHTS: dict[str, int] = {name: len(_RARITY_ORDER) - idx for idx, name in enumerate(_RARITY_ORDER)}


def weight_for_rarity(rarity: Optional[str]) -> int:
    """
    Return the numeric sort weight for a rarity string.

    Higher weights come first (most common). Unknown or falsy values fall back
    to the lowest weight so they sort last.
    """
    if rarity is None:
        return 0
    key = str(rarity).strip().lower()
    return _RARITY_WEIGHTS.get(key, 0)


T = TypeVar("T")


def sort_by_rarity_weight(
    items: Iterable[T],
    *,
    key: Callable[[T], Optional[str]] = lambda item: getattr(item, "rarity", None),
    secondary: Optional[Callable[[T], object]] = None,
) -> List[T]:
    """
    Return a new list of ``items`` sorted descending by rarity weight.

    Parameters
    ----------
    items:
        Any iterable of items to sort.
    key:
        Callable returning the rarity string for an item. Defaults to
        ``item.rarity`` which matches SQLAlchemy catalog models.
    secondary:
        Optional tiebreaker. If provided, items with the same rarity are
        further sorted ascending by this value (typically ``item.name``).
    """

    def sort_key(item: T) -> tuple:
        w = -weight_for_rarity(key(item))
        if secondary is not None:
            return (w, secondary(item))
        return (w, 0)

    return sorted(items, key=sort_key)
