"""
Scoring and ranking helpers for server events.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.database import get_owner_by_discord_id
from src.database import get_pooch_by_id as db_get_pooch_by_id

if TYPE_CHECKING:
    from src.database.models import ServerEventOccurrence, ServerEventParticipation


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
                pooch = await db_get_pooch_by_id(pooch_id)
                if pooch is not None:
                    stat = str(source.get("stat", "base_health"))
                    raw = float(getattr(pooch, stat, 0) or 0)
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
