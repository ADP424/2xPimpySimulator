"""
Pure helper functions for resolving amounts and modes from event action parameters.
No database calls — suitable for use from any event context.
"""

import random
from typing import Any


def get_amount_from_parameters(parameters: dict[str, Any], rng: random.Random) -> int:
    """Return the amount specified by the parameters, rolling randomly if min/max are given."""
    if "min_amount" in parameters and "max_amount" in parameters:
        exclude = parameters.get("exclude_amount", [])
        exclude_set = set(exclude) if isinstance(exclude, list) else set()
        lo, hi = parameters["min_amount"], parameters["max_amount"]
        candidates = [v for v in range(lo, hi + 1) if v not in exclude_set]
        return rng.choice(candidates) if candidates else lo
    return parameters.get("amount", 0)


def resolve_amount(parameters: dict[str, Any], rng: random.Random) -> tuple[int | None, bool]:
    """Return (pre_rolled_amount_or_None, roll_once). If roll_once, the amount is already rolled."""
    roll_once = bool(parameters.get("roll_once", False))
    if roll_once:
        return get_amount_from_parameters(parameters, rng), True
    return None, False


def get_mode(parameters: dict[str, Any]) -> str:
    """Return 'set' or 'modify' (default)."""
    raw = parameters.get("mode", "modify")
    return "set" if isinstance(raw, str) and raw.strip().lower() == "set" else "modify"
