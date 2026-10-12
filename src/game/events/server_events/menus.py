"""
Server event menu availability rules, shared by participation validation and every frontend.

Menus may be ORM rows or game models; both expose ``name``, ``depends_on`` and ``max_uses_per_player``.
Submissions are the dicts stored on a participation, each carrying a ``menu_name``.
"""

from __future__ import annotations

from typing import Any, Iterable


def get_used_menu_names(submissions: Iterable[dict] | None) -> set[str]:
    """Return the names of every menu the player has submitted to."""
    return {str(sub.get("menu_name", "")) for sub in (submissions or [])}


def get_use_count_per_menu(submissions: Iterable[dict] | None) -> dict[str, int]:
    """Return how many times the player has submitted to each menu."""
    counts: dict[str, int] = {}
    for sub in submissions or []:
        name = str(sub.get("menu_name", ""))
        counts[name] = counts.get(name, 0) + 1
    return counts


def get_missing_menu_prerequisite(menu: Any, used_names: set[str]) -> str | None:
    """Return the first prerequisite menu name the player hasn't used yet, or None."""
    for required in menu.depends_on or []:
        if required not in used_names:
            return required
    return None


def is_menu_exhausted(menu: Any, use_counts: dict[str, int]) -> bool:
    """Return True if the player has used the menu its maximum number of times (-1 = unlimited)."""
    return menu.max_uses_per_player >= 0 and use_counts.get(menu.name, 0) >= menu.max_uses_per_player


def get_menu_uses_left(menu: Any, use_counts: dict[str, int]) -> int | None:
    """Return how many more times the player can use the menu, or None if unlimited."""
    if menu.max_uses_per_player < 0:
        return None
    return menu.max_uses_per_player - use_counts.get(menu.name, 0)


def menu_is_available(menu: Any, used_names: set[str], use_counts: dict[str, int]) -> bool:
    """Return True if the player can currently use this menu."""
    return get_missing_menu_prerequisite(menu, used_names) is None and not is_menu_exhausted(menu, use_counts)
