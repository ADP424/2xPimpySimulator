from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .constants import (
    POOCH_STATS,
    REJUVENATION_CONSTITUTION_MULT,
    REJUVENATION_FERTILITY_MULT,
    STARVATION_PENALTY_PER_STAT,
)

_STAT_NAMES_PLUS_SIZE = list(POOCH_STATS) + ["size", "base_health"]


@dataclass
class StatSource:
    """One contribution to a stat's effective value."""

    source_type: str  # "breed" | "mutation" | "injury" | "disease" | "system"
    source_name: str
    operation: str  # "add" | "mult"
    delta: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "operation": self.operation,
            "delta": self.delta,
        }


def effective_size(pooch: Any) -> int:
    """Female pooches are one size smaller. Clamped to a minimum of 1."""
    base = int(getattr(pooch, "size", 10) or 10)
    if str(getattr(pooch, "sex", "")).lower() == "female":
        return max(1, base - 1)
    return max(1, base)


def _add_param(
    breakdown: dict[str, list[StatSource]],
    source_type: str,
    source_name: str,
    params: dict | None,
) -> None:
    """Walk a parameters dict and emit StatSource entries for every recognized key."""
    if not params:
        return
    for key, value in params.items():
        if not isinstance(value, (int, float)):
            continue
        for stat in _STAT_NAMES_PLUS_SIZE:
            if key == f"{stat}_add":
                breakdown.setdefault(stat, []).append(StatSource(source_type, source_name, "add", float(value)))
            elif key == f"{stat}_mult":
                breakdown.setdefault(stat, []).append(StatSource(source_type, source_name, "mult", float(value)))


def _apply_breakdown(base: float, sources: list[StatSource]) -> float:
    """Apply additive sources first, then multiplicative ones."""
    add_total = sum(s.delta for s in sources if s.operation == "add")
    mult_total = 1.0
    for s in sources:
        if s.operation == "mult":
            mult_total *= s.delta
    return (base + add_total) * mult_total


def compute_effective_stats(
    pooch: Any,
    *,
    breeds: Iterable[Any] = (),
    mutations: Iterable[Any] = (),
    injuries: Iterable[Any] = (),
    diseases: Iterable[Any] = (),
    return_breakdown: bool = False,
) -> dict[str, Any]:
    """
    Compute effective stats for a pooch.

    Parameters
    ----------
    pooch:
        A pooch-like object with all base stat attributes.
    breeds, mutations, injuries, diseases:
        Iterables of associated entities. Each should have a ``parameters``
        dict and a ``name`` attribute.
    return_breakdown:
        When True, the returned dict has structured per-source detail for
        snapshots / Detailed Workup.

    Returns
    -------
    dict
        Either ``{stat: int_value}`` or ``{stat: {base, effective, sources}}``.
    """
    base_values: dict[str, float] = {stat: float(getattr(pooch, stat, 10) or 10) for stat in POOCH_STATS}
    base_values["size"] = float(getattr(pooch, "size", 10) or 10)
    base_values["base_health"] = float(getattr(pooch, "base_health", 10) or 10)

    breakdown: dict[str, list[StatSource]] = {stat: [] for stat in base_values}

    # Female-size adjustment recorded as a system source so it shows up in
    # the workup breakdown. Effective size is base - 1, clamped to 1.
    if str(getattr(pooch, "sex", "")).lower() == "female":
        breakdown["size"].append(StatSource("system", "Female adjustment", "add", -1))

    for breed in breeds:
        _add_param(breakdown, "breed", getattr(breed, "name", "?"), getattr(breed, "parameters", None))
    for mut in mutations:
        _add_param(breakdown, "mutation", getattr(mut, "name", "?"), getattr(mut, "parameters", None))
    for inj in injuries:
        params = getattr(inj, "parameters", None)
        # If treated, prefer the treated parameters block.
        treated = getattr(inj, "treated", None)
        if treated and isinstance(treated, dict):
            params = {**(params or {}), **treated}
        _add_param(breakdown, "injury", getattr(inj, "name", "?"), params)
    for d in diseases:
        _add_param(breakdown, "disease", getattr(d, "name", "?"), getattr(d, "parameters", None))

    # Starvation penalty: multiplicative reduction across affected stats.
    starvation = int(getattr(pooch, "starvation", 0) or 0)
    if starvation > 0:
        penalty = max(0.1, 1.0 - STARVATION_PENALTY_PER_STAT * starvation)
        for stat in ("strength", "fertility", "constitution", "aggressiveness", "base_health"):
            breakdown[stat].append(StatSource("system", f"Starvation x{starvation}", "mult", penalty))

    # Rejuvenation penalty (cumulative).
    rej = int(getattr(pooch, "rejuvenation_count", 0) or 0)
    if rej > 0:
        breakdown["fertility"].append(
            StatSource("system", f"Rejuvenated x{rej}", "mult", REJUVENATION_FERTILITY_MULT**rej)
        )
        breakdown["constitution"].append(
            StatSource("system", f"Rejuvenated x{rej}", "mult", REJUVENATION_CONSTITUTION_MULT**rej)
        )

    # Immortality: forced infertility.
    if getattr(pooch, "immortal", False):
        breakdown["fertility"].append(StatSource("system", "Immortal", "mult", 0.0))

    # Compute effective values.
    effective: dict[str, float] = {}
    for stat, base_val in base_values.items():
        effective[stat] = _apply_breakdown(base_val, breakdown[stat])
        # Stats can't be negative.
        effective[stat] = max(0.0, effective[stat])
    # Size is always at least 1 (we can't have a zero-sized pooch).
    if effective.get("size", 0) < 1:
        effective["size"] = 1.0

    if return_breakdown:
        return {
            stat: {
                "base": base_values[stat],
                "effective": effective[stat],
                "sources": [s.to_dict() for s in breakdown[stat]],
            }
            for stat in base_values
        }

    return {stat: int(round(effective[stat])) for stat in base_values}
