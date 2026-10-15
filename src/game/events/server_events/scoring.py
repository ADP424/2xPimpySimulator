"""
Scoring and ranking helpers for server events.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    get_breed_by_id,
    get_owner_by_discord_id,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    list_pooch_breed_weights,
    list_pooch_mutations,
)

from ...manage_stats import ALL_STATS, get_effective_stat

if TYPE_CHECKING:
    from src.database.models import ServerEventOccurrence, ServerEventParticipation


async def _pooch_stat(pooch_id: int, stat: str) -> Optional[float]:
    """A pooch's stat for scoring: effective for real stats (breeds, conditions, hunger...), raw for anything else."""
    if stat in ALL_STATS:
        value = await get_effective_stat(pooch_id, stat)
        return float(value) if value is not None else None
    pooch = await db_get_pooch_by_id(pooch_id)
    return float(getattr(pooch, stat, 0) or 0) if pooch is not None else None


async def compute_submission_score(
    submission: dict,
    scoring: dict,
    rng: random.Random,
) -> float:
    """Evaluate a ScoringSpec against a single submission, returning the raw score."""
    sources: list[dict] = scoring.get("sources", [])
    if not sources:
        return 0.0

    total = 0.0
    for source in sources:
        source_type = str(source.get("type", "random")).strip().lower()

        if source_type == "random":
            lo = float(source.get("min", 0.0))
            hi = float(source.get("max", 1.0))
            total += rng.uniform(lo, hi)

        elif source_type == "constant":
            total += float(source.get("value", 0.0))

        elif source_type == "pooch_stat":
            pooch_id = submission.get("selected_pooch_id")
            if pooch_id is not None:
                raw = await _pooch_stat(pooch_id, str(source.get("stat", "base_health")))
                if raw is not None:
                    pivot = float(source.get("pivot", 0.0))
                    scale = float(source.get("scale", 1.0))
                    direction = float(source.get("direction", 1.0))
                    total += (raw - pivot) * scale * direction

        elif source_type == "owner_stat":
            owner_discord_id = submission.get("owner_discord_id")
            if owner_discord_id is not None:
                owner = await get_owner_by_discord_id(owner_discord_id)
                if owner is not None:
                    stat = str(source.get("stat", "money"))
                    raw_val = getattr(owner, stat, None)
                    if raw_val is None and stat == "money":
                        raw_val = owner.dollars
                    raw = float(raw_val or 0)
                    pivot = float(source.get("pivot", 0.0))
                    scale = float(source.get("scale", 1.0))
                    direction = float(source.get("direction", 1.0))
                    total += (raw - pivot) * scale * direction

        elif source_type == "breed_match":
            # Score based on how much of the entered pooch is one of the
            # target breeds. Sum of (proportion of breed × weight).
            pooch_id = submission.get("selected_pooch_id")
            targets = [str(b).strip().lower() for b in (source.get("targets") or [])]
            weight = float(source.get("weight", 1.0))
            if pooch_id is not None and targets:
                breed_weights = await list_pooch_breed_weights(pooch_id)
                if breed_weights:
                    pooch_total = sum(w for _, w in breed_weights) or 1
                    for breed_id, w in breed_weights:
                        breed = await get_breed_by_id(breed_id)
                        if breed is None:
                            continue
                        if breed.name.strip().lower() in targets:
                            total += (float(w) / float(pooch_total)) * weight

        elif source_type == "mutation_match":
            # +weight per required mutation present, -weight per excluded.
            pooch_id = submission.get("selected_pooch_id")
            required = [str(m).strip().lower() for m in (source.get("required") or [])]
            excluded = [str(m).strip().lower() for m in (source.get("excluded") or [])]
            weight = float(source.get("weight", 1.0))
            if pooch_id is not None and (required or excluded):
                muts = [str(m.name).strip().lower() for m in (await list_pooch_mutations(pooch_id))]
                for r in required:
                    if r in muts:
                        total += weight
                for e in excluded:
                    if e in muts:
                        total -= weight

        elif source_type == "stat_target":
            # Linear/gaussian falloff from a target stat value.
            pooch_id = submission.get("selected_pooch_id")
            stat = str(source.get("stat", "base_health"))
            target = float(source.get("target", 10))
            scale = float(source.get("scale", 1.0))
            falloff = str(source.get("falloff", "linear")).strip().lower()
            max_dist = float(source.get("max_distance", 10))
            if pooch_id is not None:
                raw = await _pooch_stat(pooch_id, stat)
                if raw is not None:
                    distance = abs(raw - target)
                    if falloff == "gaussian":
                        score = math.exp(-((distance / max_dist) ** 2))
                    else:
                        score = max(0.0, 1.0 - distance / max_dist) if max_dist > 0 else 0.0
                    total += scale * score

    return total


def aggregate_player_score(per_submission_scores: list[float], aggregate: str) -> float:
    """Combine multiple submission scores using the given aggregation method."""
    if not per_submission_scores:
        return 0.0
    if aggregate == "average":
        return sum(per_submission_scores) / len(per_submission_scores)
    if aggregate == "max":
        return max(per_submission_scores)
    return sum(per_submission_scores)


async def rank_participations(
    occurrence: ServerEventOccurrence, rng: random.Random
) -> list[tuple[ServerEventParticipation, float, int]]:
    """Score and rank all participations for an occurrence."""
    scored: list[tuple[ServerEventParticipation, float, float]] = []

    for participation in occurrence.participations:
        submissions = list(participation.submissions or [])
        if not submissions:
            scored.append((participation, 0.0, rng.random()))
            continue

        per_scores: list[float] = []
        aggregate = "sum"
        for sub in submissions:
            scoring_spec = sub.get("scoring") or {}
            aggregate = str(scoring_spec.get("aggregate", aggregate)).strip().lower()
            score = await compute_submission_score(sub, scoring_spec, rng)
            per_scores.append(score)

        total_score = aggregate_player_score(per_scores, aggregate)
        scored.append((participation, total_score, rng.random()))

    ordered = sorted(scored, key=lambda item: (item[1], item[2]), reverse=True)
    return [(participation, score, index + 1) for index, (participation, score, _) in enumerate(ordered)]
