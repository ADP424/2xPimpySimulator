"""
The one place a pooch's effective stats and health are calculated.

Everything that needs a stat the way the game sees it (events, diseases, fights, the medical exam, the Detailed
Workup, health and death) goes through here, so they all agree. The database layer only fetches the rows
(``get_pooch_stat_sources``, ``get_pooch_health_impact``).

Each stat is the pooch's base value pushed through these stages in order, each stage being
``(total + adds) * mults``:

1. mutations
2. breeds, weighted by how much of the pooch each breed is (adds and mults are weighted averages)
3. injuries (an injury's ``treated`` parameters replace its normal ones once that pooch's injury is treated)
4. injury stacks (bonuses for having several of the same injury)
5. diseases
6. the pooch's own state: hunger, rejuvenations, immortality (infertile) and being female (one size smaller)

Results are never negative, and size is at least 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from src.database import get_pooch_health_impact, get_pooch_stat_sources

from .constants import (
    POOCH_STATS,
    REJUVENATION_CONSTITUTION_MULT,
    REJUVENATION_FERTILITY_MULT,
    STARVATION_PENALTY_PER_STAT,
)
from .utils.obfuscation import starvation_label

ALL_STATS = (*POOCH_STATS, "size", "base_health")
STARVATION_AFFECTED_STATS = ("strength", "fertility", "constitution", "aggressiveness", "base_health")
MIN_STARVATION_MULT = 0.1


@dataclass
class StatSource:
    """One contribution to a stat: an add or a mult from a breed, mutation, injury, disease or the pooch itself."""

    source_type: str  # "mutation" | "breed" | "injury" | "disease" | "system"
    source_name: str
    operation: str  # "add" | "mult"
    delta: float
    weight: Optional[float] = None  # for breeds: the share of the pooch that breed makes up

    def describe(self) -> str:
        """Player-facing text, e.g. "Broken Leg -3", "Poodle x0.8 (60%)", "Immortal x0"."""
        if self.operation == "add":
            return f"{self.source_name} {round(self.delta, 1):+g}"
        text = f"{self.source_name} x{round(self.delta, 2):g}"
        if self.weight is not None:
            text += f" ({round(self.weight * 100):d}%)"
        return text

    def to_dict(self) -> dict[str, Any]:
        data = {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "operation": self.operation,
            "delta": self.delta,
            "text": self.describe(),
        }
        if self.weight is not None:
            data["weight"] = self.weight
        return data


STAT_LABELS = {stat: stat.replace("_", " ").title() for stat in ALL_STATS} | {"base_health": "Health"}

# Catalog parameters that change something other than a stat, as (key prefix, label). A prefix takes the same
# ``_add``/``_mult`` suffixes as a stat; "breeding_cooldown" is a bare add.
OTHER_EFFECT_LABELS = (
    ("dollar_value", "Sale Value"),
    ("bloodskull_value", "Bloodskull Value"),
)

# Effects where going up is worse for the owner, and ones that are neither good nor bad
_HARMFUL_WHEN_RAISED = {"breeding_cooldown"}
_NEUTRAL_EFFECTS = {"size", "aggressiveness"}


def _stat_effect(key: str, label: str, operation: str, value: float) -> dict[str, Any]:
    if operation == "add":
        text, raised = f"{round(value, 2):+g}", value > 0
    else:
        text, raised = f"×{round(value, 2):g}", value > 1
    if key in _NEUTRAL_EFFECTS:
        beneficial = None
    else:
        beneficial = raised != (key in _HARMFUL_WHEN_RAISED)
    return {
        "key": key,
        "label": label,
        "operation": operation,
        "value": value,
        "text": text,
        "direction": "up" if raised else "down",
        "beneficial": beneficial,
    }


def describe_stat_effects(parameters: Optional[dict]) -> list[dict[str, Any]]:
    """
    List what a breed's or mutation's parameters do to a pooch, for the catalog.

    Each entry is ``{key, label, operation, value, text, direction, beneficial}``, e.g. Gigantism's strength gives
    ``label="Strength", text="×1.5", direction="up", beneficial=True``. ``beneficial`` is None for effects that are
    neither good nor bad (size, aggressiveness). Stats come first in ``ALL_STATS`` order, adds before mults;
    parameters that change nothing (+0, ×1) are left out.
    """

    params = parameters or {}
    effects = []
    for key, label in (*STAT_LABELS.items(), *OTHER_EFFECT_LABELS):
        add, mult = _stat_params(params, key)
        if add:
            effects.append(_stat_effect(key, label, "add", add))
        if mult != 1.0:
            effects.append(_stat_effect(key, label, "mult", mult))
    cooldown = float(params.get("breeding_cooldown", 0) or 0)
    if cooldown:
        effects.append(_stat_effect("breeding_cooldown", "Breeding Cooldown", "add", cooldown))
    return effects


def effective_size(pooch: Any) -> int:
    """Female pooches are one size smaller. Clamped to a minimum of 1."""
    base = int(getattr(pooch, "size", 10) or 10)
    if str(getattr(pooch, "sex", "")).lower() == "female":
        return max(1, base - 1)
    return max(1, base)


def _catalog(instance: Any, attr: str) -> Any:
    """Return the catalog row behind a pooch's mutation/injury/disease instance (or the row itself if given one)."""
    return getattr(instance, attr, None) or instance


def _default_label(kind: str, instance: Any) -> str:
    return getattr(_catalog(instance, kind), "name", "?")


def _stat_params(params: Optional[dict], stat: str) -> tuple[float, float]:
    params = params or {}
    return float(params.get(f"{stat}_add", 0) or 0), float(params.get(f"{stat}_mult", 1.0))


def compute_effective_stats(
    pooch: Any,
    *,
    mutations: Iterable[Any] = (),
    breeds: Iterable[Any] = (),
    injuries: Iterable[Any] = (),
    diseases: Iterable[Any] = (),
    return_breakdown: bool = False,
    label: Callable[[str, Any], str] = _default_label,
) -> dict[str, Any]:
    """
    Compute a pooch's effective stats (see the module docstring for the rules).

    Parameters
    ----------
    pooch:
        The pooch, with its base stats, ``sex``, ``starvation``, ``rejuvenation_count`` and ``immortal``.
    mutations, injuries, diseases:
        The pooch's mutation/injury/disease instances (``PoochMutation`` etc.). Catalog rows also work; an injury
        given as a catalog row is treated as untreated.
    breeds:
        ``(breed, weight)`` pairs. A bare breed counts with weight 1.
    return_breakdown:
        When True, return ``{stat: {base, effective, sources}}`` instead of ``{stat: int}``.
    label:
        Names a source in the breakdown: ``label(kind, instance)`` with kind "mutation", "injury" or "disease".
        Callers showing players a breakdown pass one that hides undiagnosed conditions behind their symptom.
    """

    mutations, injuries, diseases = list(mutations), list(injuries), list(diseases)
    breed_rows = [row if isinstance(row, tuple) else (row, 1.0) for row in breeds]
    total_weight = sum(float(weight) for _, weight in breed_rows)

    injury_counts: dict[Any, tuple[Any, int]] = {}
    for instance in injuries:
        injury = _catalog(instance, "injury")
        key = getattr(injury, "id", id(injury))
        injury_counts[key] = (injury, injury_counts.get(key, (injury, 0))[1] + 1)

    starvation = int(getattr(pooch, "starvation", 0) or 0)
    rejuvenations = int(getattr(pooch, "rejuvenation_count", 0) or 0)
    is_female = str(getattr(pooch, "sex", "")).lower() == "female"
    is_immortal = bool(getattr(pooch, "immortal", False))

    results: dict[str, Any] = {}
    for stat in ALL_STATS:
        base = float(getattr(pooch, stat, 10) if getattr(pooch, stat, None) is not None else 10)
        total = base
        sources: list[StatSource] = []

        def stage(entries: list[StatSource]) -> None:
            nonlocal total
            adds = sum(e.delta for e in entries if e.operation == "add")
            mult = 1.0
            for e in entries:
                if e.operation == "mult":
                    mult *= e.delta
            total = (total + adds) * mult
            sources.extend(
                e for e in entries if (e.operation == "add" and e.delta) or (e.operation == "mult" and e.delta != 1.0)
            )

        def from_params(kind: str, name: str, params: Optional[dict]) -> list[StatSource]:
            add, mult = _stat_params(params, stat)
            return [StatSource(kind, name, "add", add), StatSource(kind, name, "mult", mult)]

        # 1. mutations
        stage(
            [
                e
                for m in mutations
                for e in from_params("mutation", label("mutation", m), _catalog(m, "mutation").parameters)
            ]
        )

        # 2. breeds (weighted averages: the weighted mults are summed, not multiplied)
        if total_weight > 0:
            adds, mult_sum, shown = 0.0, 0.0, []
            for breed, weight in breed_rows:
                share = float(weight) / total_weight
                add, mult = _stat_params(breed.parameters, stat)
                adds += add * share
                mult_sum += mult * share
                name = getattr(breed, "name", "?")
                if add:
                    shown.append(StatSource("breed", name, "add", add * share, weight=share))
                if mult != 1.0:
                    shown.append(StatSource("breed", name, "mult", mult, weight=share))
            total = (total + adds) * mult_sum
            sources.extend(shown)

        # 3. injuries (a treated injury uses its treated parameters, falling back to the normal mult)
        injury_entries = []
        for instance in injuries:
            injury = _catalog(instance, "injury")
            params = injury.parameters or {}
            name = label("injury", instance)
            treated_params = getattr(injury, "treated", None)
            if instance is not injury and getattr(instance, "treated", False) and isinstance(treated_params, dict):
                add = float(treated_params.get(f"{stat}_add", 0) or 0)
                mult = float(treated_params.get(f"{stat}_mult", params.get(f"{stat}_mult", 1.0)))
                injury_entries += [
                    StatSource("injury", f"{name} (treated)", "add", add),
                    StatSource("injury", f"{name} (treated)", "mult", mult),
                ]
            else:
                injury_entries += from_params("injury", name, params)
        stage(injury_entries)

        # 4. injury stacks
        stack_entries = []
        for injury, count in injury_counts.values():
            for entry in (injury.parameters or {}).get("stacks", []) or []:
                min_count, max_count = entry.get("min_count", 1), entry.get("max_count")
                if count >= min_count and (max_count is None or count <= max_count):
                    stack_entries += from_params("injury", f"{injury.name} x{count}", entry)
        stage(stack_entries)

        # 5. diseases
        stage(
            [
                e
                for d in diseases
                for e in from_params("disease", label("disease", d), _catalog(d, "disease").parameters)
            ]
        )

        # 6. the pooch's own state
        system = []
        if starvation > 0 and stat in STARVATION_AFFECTED_STATS:
            penalty = max(MIN_STARVATION_MULT, 1.0 - STARVATION_PENALTY_PER_STAT * starvation)
            system.append(StatSource("system", f"Hunger ({starvation_label(starvation)})", "mult", penalty))
        if rejuvenations > 0 and stat == "fertility":
            system.append(
                StatSource(
                    "system", f"Rejuvenated x{rejuvenations}", "mult", REJUVENATION_FERTILITY_MULT**rejuvenations
                )
            )
        if rejuvenations > 0 and stat == "constitution":
            system.append(
                StatSource(
                    "system", f"Rejuvenated x{rejuvenations}", "mult", REJUVENATION_CONSTITUTION_MULT**rejuvenations
                )
            )
        if is_immortal and stat == "fertility":
            system.append(StatSource("system", "Immortal", "mult", 0.0))
        if is_female and stat == "size":
            system.append(StatSource("system", "Female", "add", -1))
        stage(system)

        effective = max(0.0, total)
        if stat == "size":
            effective = max(1.0, effective)
        results[stat] = (base, effective, sources)

    if return_breakdown:
        return {
            stat: {"base": base, "effective": effective, "sources": [s.to_dict() for s in sources]}
            for stat, (base, effective, sources) in results.items()
        }
    return {stat: int(round(effective)) for stat, (_, effective, _) in results.items()}


async def get_effective_stats(pooch_id: int, *, return_breakdown: bool = False, label=_default_label) -> Optional[dict]:
    """Fetch a pooch's stat sources and compute its effective stats. Returns None if the pooch doesn't exist."""
    sources = await get_pooch_stat_sources(pooch_id)
    if sources is None:
        return None
    pooch, mutations, breeds, injuries, diseases = sources
    return compute_effective_stats(
        pooch,
        mutations=mutations,
        breeds=breeds,
        injuries=injuries,
        diseases=diseases,
        return_breakdown=return_breakdown,
        label=label,
    )


async def get_effective_stat(pooch_id: int, stat: str) -> Optional[int]:
    """Return one of a pooch's effective stats (or ``base_health``), or None if the pooch doesn't exist."""
    stats = await get_effective_stats(pooch_id)
    return None if stats is None else stats[stat]


async def get_pooch_health(pooch_id: int) -> Optional[int]:
    """
    Return a pooch's current health: effective base health, minus health lost to age, plus the health impact of its
    mutations, injuries and diseases. Returns None if the pooch doesn't exist.
    """

    sources = await get_pooch_stat_sources(pooch_id)
    if sources is None:
        return None
    pooch, mutations, breeds, injuries, diseases = sources
    stats = compute_effective_stats(pooch, mutations=mutations, breeds=breeds, injuries=injuries, diseases=diseases)
    return stats["base_health"] - int(pooch.health_loss_age or 0) + await get_pooch_health_impact(pooch_id)
