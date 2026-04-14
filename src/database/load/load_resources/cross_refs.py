"""
Resource cross-reference resolution and validation.

JSONC resources refer to each other by name (never by numeric id — ids are
an internal DB concern). After all catalogs have loaded this module walks
every entity that holds a name reference and:

1. Verifies each referenced name exists in the target catalog.
2. Builds name↔id indices that runtime code can consult without re-scanning
   strings.

The registry is a module-level singleton; tests can rebuild it in-memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from src.database.session import session_scope
from src.logger import get_logger

from ...models import Disease, Injury, Mutation
from .utils import ResourceValidationError

logger = get_logger("database/load/load_resources/cross_refs")


@dataclass
class ResourceRegistry:
    """
    Name-keyed lookups for resource entities.

    All names are stored lowercase for case-insensitive matching. Callers
    should normalize with ``.lower()`` before indexing.
    """

    mutation_id_by_name: dict[str, int] = field(default_factory=dict)
    disease_id_by_name: dict[str, int] = field(default_factory=dict)
    injury_id_by_name: dict[str, int] = field(default_factory=dict)
    mutation_by_id: dict[int, Any] = field(default_factory=dict)
    disease_by_id: dict[int, Any] = field(default_factory=dict)
    injury_by_id: dict[int, Any] = field(default_factory=dict)

    def mutation_id(self, name: str | None) -> int | None:
        if name is None:
            return None
        return self.mutation_id_by_name.get(str(name).strip().lower())

    def disease_id(self, name: str | None) -> int | None:
        if name is None:
            return None
        return self.disease_id_by_name.get(str(name).strip().lower())

    def injury_id(self, name: str | None) -> int | None:
        if name is None:
            return None
        return self.injury_id_by_name.get(str(name).strip().lower())


_REGISTRY: ResourceRegistry | None = None


def get_resource_registry() -> ResourceRegistry:
    """
    Return the current registry. Raises if ``build_resource_registry`` has
    not been called yet (which happens during ``load_resources.main``).
    """
    if _REGISTRY is None:
        raise RuntimeError("ResourceRegistry not initialized. Call build_resource_registry() first.")
    return _REGISTRY


def set_resource_registry(registry: ResourceRegistry) -> None:
    """Install a registry. Primarily used by tests."""
    global _REGISTRY
    _REGISTRY = registry


async def build_resource_registry() -> ResourceRegistry:
    """
    Build the registry from the currently-loaded catalog tables and
    validate every cross-reference we know about.
    """
    async with session_scope() as session:
        mutations = list((await session.execute(select(Mutation))).scalars().all())
        diseases = list((await session.execute(select(Disease))).scalars().all())
        injuries = list((await session.execute(select(Injury))).scalars().all())

    registry = ResourceRegistry()
    for m in mutations:
        registry.mutation_id_by_name[m.name.strip().lower()] = m.id
        registry.mutation_by_id[m.id] = m
    for d in diseases:
        registry.disease_id_by_name[d.name.strip().lower()] = d.id
        registry.disease_by_id[d.id] = d
    for inj in injuries:
        registry.injury_id_by_name[inj.name.strip().lower()] = inj.id
        registry.injury_by_id[inj.id] = inj

    errors: list[str] = []

    # Validate mutation cross-references.
    for m in mutations:
        params = m.parameters or {}

        for key in ("incompatible_mutations",):
            refs = params.get(key)
            if refs is None:
                continue
            if not isinstance(refs, list):
                errors.append(f"mutation.{m.name}.parameters.{key}: must be a list")
                continue
            for ref in refs:
                if not isinstance(ref, str) or registry.mutation_id(ref) is None:
                    errors.append(f"mutation.{m.name}.parameters.{key}: unknown mutation '{ref}'")

        for key in ("disease_predispositions", "disease_immunities", "incompatible_diseases"):
            refs = params.get(key)
            if refs is None:
                continue
            if not isinstance(refs, list):
                errors.append(f"mutation.{m.name}.parameters.{key}: must be a list")
                continue
            for ref in refs:
                if not isinstance(ref, str) or registry.disease_id(ref) is None:
                    errors.append(f"mutation.{m.name}.parameters.{key}: unknown disease '{ref}'")

        # on_death_options: list of injury names if present.
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
                if not isinstance(injury_name, str) or registry.injury_id(injury_name) is None:
                    errors.append(f"mutation.{m.name}.on_death_options: unknown injury '{injury_name}'")

    if errors:
        joined = "\n".join(f"- {e}" for e in errors)
        raise ResourceValidationError(f"Resource cross-reference errors:\n{joined}")

    set_resource_registry(registry)
    logger.info(
        "Built resource registry: %d mutations, %d diseases, %d injuries.",
        len(registry.mutation_id_by_name),
        len(registry.disease_id_by_name),
        len(registry.injury_id_by_name),
    )
    return registry
