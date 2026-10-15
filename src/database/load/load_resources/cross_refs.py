"""
Resource cross-reference validation.

JSONC resources refer to each other by name (never by numeric id — ids are an internal DB concern). After all
catalogs have loaded, ``validate_cross_references`` checks that every name a mutation refers to exists in its
target catalog, and fails the load with every problem listed if not.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.database.session import session_scope
from src.logger import get_logger

from ...models import Disease, Injury, Mutation
from .utils import ResourceValidationError

logger = get_logger("database/load/load_resources/cross_refs")


def _names(rows: list[Any]) -> set[str]:
    return {row.name.strip().lower() for row in rows}


def find_cross_reference_errors(mutations: list[Any], disease_names: set[str], injury_names: set[str]) -> list[str]:
    """
    Return one message per mutation parameter that refers to an unknown mutation, disease or injury.

    Names are matched case-insensitively.
    """

    mutation_names = _names(mutations)
    targets = {
        "incompatible_mutations": ("mutation", mutation_names),
        "disease_predispositions": ("disease", disease_names),
        "disease_immunities": ("disease", disease_names),
        "incompatible_diseases": ("disease", disease_names),
    }

    errors: list[str] = []
    for m in mutations:
        params = m.parameters or {}

        for key, (kind, known) in targets.items():
            refs = params.get(key)
            if refs is None:
                continue
            if not isinstance(refs, list):
                errors.append(f"mutation.{m.name}.parameters.{key}: must be a list")
                continue
            for ref in refs:
                if not isinstance(ref, str) or ref.strip().lower() not in known:
                    errors.append(f"mutation.{m.name}.parameters.{key}: unknown {kind} '{ref}'")

        # on_death_options: injury names for the "injure" death effect
        for trigger in params.get("on_death_triggers", []) or []:
            if not isinstance(trigger, dict):
                continue
            options = trigger.get("on_death_options")
            if options is None:
                continue
            if not isinstance(options, list):
                errors.append(f"mutation.{m.name}.parameters.on_death_triggers.on_death_options: must be a list")
                continue
            for injury_name in options:
                if not isinstance(injury_name, str) or injury_name.strip().lower() not in injury_names:
                    errors.append(f"mutation.{m.name}.on_death_options: unknown injury '{injury_name}'")
    return errors


async def validate_cross_references() -> None:
    """Validate every name-based cross reference between the loaded catalogs. Raises ResourceValidationError."""
    async with session_scope() as session:
        mutations = list((await session.execute(select(Mutation))).scalars().all())
        diseases = list((await session.execute(select(Disease))).scalars().all())
        injuries = list((await session.execute(select(Injury))).scalars().all())

    errors = find_cross_reference_errors(mutations, _names(diseases), _names(injuries))
    if errors:
        joined = "\n".join(f"- {e}" for e in errors)
        raise ResourceValidationError(f"Resource cross-reference errors:\n{joined}")
    logger.info(
        "Validated resource cross-references: %d mutations, %d diseases, %d injuries.",
        len(mutations),
        len(diseases),
        len(injuries),
    )
