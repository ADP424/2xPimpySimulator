from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from src.database import get_breed_by_id, get_mutation_by_id, get_pooch_by_id

if TYPE_CHECKING:
    from .event_context import EventContext
    from .event_result import EventResult


EventEntityKind = Literal["pooches", "breeds", "mutations"]


@dataclass(frozen=True)
class EventEntityReference:
    id: int
    label: str
    description: str | None = None


@dataclass
class EventEntityReferences:
    pooches: list[EventEntityReference] = field(default_factory=list)
    breeds: list[EventEntityReference] = field(default_factory=list)
    mutations: list[EventEntityReference] = field(default_factory=list)

    def for_kind(self, kind: EventEntityKind) -> list[EventEntityReference]:
        return getattr(self, kind)

    def copy(self) -> EventEntityReferences:
        return EventEntityReferences(
            pooches=list(self.pooches),
            breeds=list(self.breeds),
            mutations=list(self.mutations),
        )

    def add(self, kind: EventEntityKind, reference: EventEntityReference) -> None:
        bucket = self.for_kind(kind)
        if all(existing.id != reference.id for existing in bucket):
            bucket.append(reference)

    def has_items(self) -> bool:
        return bool(self.pooches or self.breeds or self.mutations)


async def resolve_event_entity_references(
    context: EventContext,
    result: EventResult | None = None,
    existing: EventEntityReferences | None = None,
) -> EventEntityReferences:
    """
    Resolve typed entity references for an event context and optional result.

    Parameters
    ----------
    context: EventContext
        The event context carrying selected and affected entity ids.

    result: EventResult | None
        Optional event result to inspect for created / affected entities.

    existing: EventEntityReferences | None
        Existing references to preserve and extend.

    Returns
    -------
    EventEntityReferences
        Typed entity references for the event.
    """

    references = existing.copy() if existing is not None else EventEntityReferences()

    seen_ids: dict[EventEntityKind, set[int]] = {
        "pooches": {reference.id for reference in references.pooches},
        "breeds": {reference.id for reference in references.breeds},
        "mutations": {reference.id for reference in references.mutations},
    }

    pooch_ids: set[int] = set(context.affected_pooch_ids)
    if context.selected_pooch_id is not None:
        pooch_ids.add(context.selected_pooch_id)

    breed_ids: set[int] = set()
    mutation_ids: set[int] = set()

    if result is not None:
        pooch_ids.update(pooch_id for pooch_id in result.pooches_affected)
        pooch_ids.update(pooch_id for pooch_id in result.pooches_created)
        pooch_ids.update(pooch_id for pooch_id in result.pooches_killed)
        mutation_ids.update(mutation_id for _pooch_id, mutation_id in result.mutations_added)
        mutation_ids.update(mutation_id for _pooch_id, mutation_id in result.mutations_removed)

        extra = result.extra_data or {}

        for entry in _normalize_detail_entries(extra.get("health_changes"), id_key="pooch_id", value_key="amount"):
            if entry.get("pooch_id") is not None:
                pooch_ids.add(entry["pooch_id"])

        for entry in _normalize_detail_entries(extra.get("age_changes"), id_key="pooch_id", value_key="amount"):
            if entry.get("pooch_id") is not None:
                pooch_ids.add(entry["pooch_id"])

        for key in ("created_pooches", "killed_pooches", "renamed_pooches", "transferred_pooches", "breeds_added"):
            for entry in _iter_dict_entries(extra.get(key)):
                if entry.get("pooch_id") is not None:
                    pooch_ids.add(entry["pooch_id"])
                if entry.get("breed_id") is not None:
                    breed_ids.add(entry["breed_id"])

        for key in ("mutations_added_details", "mutations_removed_details"):
            for entry in _iter_dict_entries(extra.get(key)):
                if entry.get("pooch_id") is not None:
                    pooch_ids.add(entry["pooch_id"])
                if entry.get("mutation_id") is not None:
                    mutation_ids.add(entry["mutation_id"])

    for pooch_id in sorted(pooch_ids):
        if pooch_id in seen_ids["pooches"]:
            continue
        pooch = await get_pooch_by_id(pooch_id)
        label = pooch.name if pooch is not None else f"Pooch #{pooch_id}"
        references.add("pooches", EventEntityReference(id=pooch_id, label=label))
        seen_ids["pooches"].add(pooch_id)

    for breed_id in sorted(breed_ids):
        if breed_id in seen_ids["breeds"]:
            continue
        breed = await get_breed_by_id(breed_id)
        label = breed.name if breed is not None else f"Breed #{breed_id}"
        references.add("breeds", EventEntityReference(id=breed_id, label=label))
        seen_ids["breeds"].add(breed_id)

    for mutation_id in sorted(mutation_ids):
        if mutation_id in seen_ids["mutations"]:
            continue
        mutation = await get_mutation_by_id(mutation_id)
        label = mutation.name if mutation is not None else f"Mutation #{mutation_id}"
        references.add("mutations", EventEntityReference(id=mutation_id, label=label))
        seen_ids["mutations"].add(mutation_id)

    return references


def _iter_dict_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _normalize_detail_entries(value: Any, *, id_key: str, value_key: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]

    if isinstance(value, dict):
        rows: list[dict[str, Any]] = []
        for raw_id, raw_value in value.items():
            try:
                rows.append({id_key: raw_id, value_key: raw_value})
            except TypeError, ValueError:
                continue
        return rows

    return []
