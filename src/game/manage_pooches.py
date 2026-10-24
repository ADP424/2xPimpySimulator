from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from src.database import (
    create_pooch_snapshot,
    decrement_pooch_breeding_cooldown,
    get_owner_by_discord_id,
    get_parentage_maps,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_pooch_injury_instance,
    get_pooch_parents,
    give_money_to_owner,
    list_invisible_pooch_injury_instances,
    list_invisible_pooch_mutation_instances,
    list_persistent_injury_instances,
    list_pooch_children,
    list_pooch_ids_on_breeding_cooldown,
    list_pooch_injury_instances,
    list_pooch_mutation_instances,
    list_pooch_siblings,
)
from src.database import list_pooch_snapshots as db_list_pooch_snapshots
from src.database import (
    list_pooches_with_health,
    reduce_pooch_injury_persistence,
)
from src.database import rename_pooch as db_rename_pooch
from src.database import (
    reveal_pooch_injury,
    reveal_pooch_mutation,
    set_pooch_vet_checked,
    treat_pooch_injury,
)
from src.database.models import (
    SNAPSHOT_MEDICAL_EXAM,
    SNAPSHOT_VET_DISEASES,
    SNAPSHOT_VET_INJURIES,
    SNAPSHOT_VET_MUTATIONS,
    PoochInjury,
)
from src.logger import get_logger

from .constants import (
    BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR,
    INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR,
    INJURY_SEVERITIES,
    MAX_NAME_LENGTH,
    VET_DIAGNOSE_INJURIES_COST,
    VET_DIAGNOSE_MUTATIONS_COST,
    VET_TREATMENT_BASE_COST,
    VET_TREATMENT_PERSISTENCE_REDUCTION,
    VET_TREATMENT_SEVERITY_COST_PER_LEVEL,
)
from .exceptions import PoochNotFound
from .manage_static import get_disease_by_id, get_injury_by_id, get_mutation_by_id
from .manage_stats import get_effective_stat, get_effective_stats
from .models import PoochTimelineEntry, get_pooch_status, to_pooch

logger = get_logger("game/manage_pooches")

if TYPE_CHECKING:
    from .models import Pooch


async def get_pooch_family_tree(pooch_id: int, ancestor_depth: int = 5, descendant_depth: int = 2) -> dict:
    """
    Build a family tree graph (nodes + edges) for a pooch, traversing ancestors upward
    and descendants downward. Each pooch appears as a single node even if it occurs
    at multiple generations (inbreeding).

    Returns
    -------
    dict
        ``{"root_id": int, "nodes": list[dict], "edges": list[dict]}``
        Each node: ``{id, name, sex, alive, age, status, generation}``
        Each edge: ``{source, target}`` where source is the parent.
    """
    # Phase 1: Load relevant parentage via recursive CTE (1 query)
    parents_of, children_of = await get_parentage_maps(pooch_id, ancestor_depth, descendant_depth)

    # Phase 2: In-memory traversal to collect pooch IDs, edges, and generations
    needed_ids: set[int] = set()
    edges: set[tuple[int, int]] = set()
    node_generation: dict[int, int] = {}
    ancestor_explored: dict[int, int] = {}
    descendant_explored: dict[int, int] = {}

    def _mark_node(pid: int, generation: int):
        needed_ids.add(pid)
        if pid not in node_generation or generation > node_generation[pid]:
            node_generation[pid] = generation

    def _traverse_ancestors(pid: int, depth: int, generation: int):
        if depth <= 0:
            return
        if ancestor_explored.get(pid, -1) >= depth:
            return
        ancestor_explored[pid] = depth

        father_id, mother_id = parents_of.get(pid, (None, None))
        for parent_id in (father_id, mother_id):
            if parent_id is None:
                continue
            edges.add((parent_id, pid))
            _mark_node(parent_id, generation)
            _traverse_ancestors(parent_id, depth - 1, generation + 1)

    def _traverse_descendants(pid: int, depth: int, generation: int):
        if depth <= 0:
            return
        if descendant_explored.get(pid, -1) >= depth:
            return
        descendant_explored[pid] = depth

        for child_id in children_of.get(pid, []):
            edges.add((pid, child_id))
            _mark_node(child_id, generation)

            # Also include the child's other parent (mate)
            father_id, mother_id = parents_of.get(child_id, (None, None))
            for parent_id in (father_id, mother_id):
                if parent_id is not None and parent_id != pid:
                    if parent_id in node_generation:
                        _mark_node(parent_id, node_generation[parent_id])
                    else:
                        _mark_node(parent_id, node_generation.get(pid, 0))
                    edges.add((parent_id, child_id))

            _traverse_descendants(child_id, depth - 1, generation - 1)

    # Root
    _mark_node(pooch_id, 0)
    _traverse_ancestors(pooch_id, ancestor_depth, 1)
    _traverse_descendants(pooch_id, descendant_depth, -1)

    # Siblings of root
    father_id, mother_id = parents_of.get(pooch_id, (None, None))
    if father_id and mother_id:
        for candidate_id, (f, m) in parents_of.items():
            if candidate_id != pooch_id and f == father_id and m == mother_id:
                _mark_node(candidate_id, 0)
                edges.add((father_id, candidate_id))
                edges.add((mother_id, candidate_id))

    # Phase 3: Batch-fetch all needed pooches + health in one joined query
    pooches = await list_pooches_with_health(needed_ids)

    # Verify root exists
    if pooch_id not in pooches:
        raise PoochNotFound(f"Pooch {pooch_id} not found.")

    # Ensure every child is strictly below ALL its parents
    changed = True
    while changed:
        changed = False
        for source, target in edges:
            parent_gen = node_generation.get(source, 0)
            child_gen = node_generation.get(target, 0)
            if child_gen >= parent_gen:
                node_generation[target] = parent_gen - 1
                changed = True

    # Build node dicts (sorted by ID to match creation order for stable layout)
    nodes = []
    for pid in sorted(needed_ids):
        p = pooches.get(pid)
        if p is None:
            continue
        nodes.append(
            {
                "id": p["id"],
                "name": p["name"],
                "sex": p["sex"],
                "alive": p["alive"],
                "age": p["age"],
                "status": get_pooch_status(p["alive"], p["age"], p["health"]),
                "generation": node_generation.get(pid, 0),
            }
        )

    # Compute incest levels for each mating pair
    from .breeding import calculate_incest_level

    parent_pairs: dict[tuple[int, int], set[int]] = {}
    edge_by_child: dict[int, list[int]] = {}
    for src, tgt in edges:
        edge_by_child.setdefault(tgt, []).append(src)
    for child_id, parents in edge_by_child.items():
        if len(parents) == 2:
            pair = (min(parents), max(parents))
            parent_pairs.setdefault(pair, set()).add(child_id)

    couples = []
    for (a_id, b_id), children_ids in parent_pairs.items():
        incest_level = await calculate_incest_level(a_id, b_id)
        couples.append(
            {
                "parents": [a_id, b_id],
                "children": list(children_ids),
                "incest_level": round(incest_level, 4),
            }
        )

    return {
        "root_id": pooch_id,
        "nodes": nodes,
        "edges": [{"source": s, "target": t} for s, t in edges],
        "couples": couples,
    }


async def get_pooch_by_id(pooch_id: int) -> Pooch:
    """
    Return a pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to return.

    Returns
    -------
    Pooch
        The pooch with the given ID.

    Raises
    ------
    PoochNotFound
        When a Pooch with `pooch_id` is not found.
    """

    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        raise PoochNotFound(f"Pooch {pooch_id} not found.")
    return await to_pooch(pooch)


async def get_pooch_family(pooch_id: int) -> dict[str, list[Pooch]]:
    """
    Get the immediate family (parents, children, full siblings) of the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the family of.

    Returns
    -------
    dict[str, list[Pooch]]
        A dictionary in the form `{ "parents": list[Pooch], "children": list[Pooch], "siblings": list[Pooch] }`.
    """

    father, mother = await get_pooch_parents(pooch_id)
    parents = [(await to_pooch(parent)) for parent in (father, mother) if parent is not None]

    children_orm = await list_pooch_children(pooch_id)
    children = [(await to_pooch(child)) for child in children_orm]

    siblings_orm = await list_pooch_siblings(pooch_id)
    siblings = [(await to_pooch(sibling)) for sibling in siblings_orm]

    return {
        "parents": parents,
        "children": children,
        "siblings": siblings,
    }


async def run_hourly_breeding_cooldown_check(rng_seed: Optional[int] = None) -> int:
    """
    Roll a fertility-based chance to decrement each living pooch's breeding cooldown by 1.
    Pregnant pooches are skipped: their cooldown waits until the litter is born (birth resets it anyway).

    Chance per pooch = fertility / BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR.

    Parameters
    ----------
    rng_seed: int, optional
        Seed for reproducible rolls.

    Returns
    -------
    int
        Number of pooches whose cooldown was decremented.
    """

    import random as _random

    rng = _random.Random(rng_seed)
    decremented = 0
    for pooch_id in await list_pooch_ids_on_breeding_cooldown():
        # Effective fertility: immortal pooches (fertility 0) never come back into heat
        fertility = await get_effective_stat(pooch_id, "fertility") or 0
        if rng.random() < fertility / BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR:
            await decrement_pooch_breeding_cooldown(pooch_id)
            decremented += 1
    logger.info("Hourly breeding cooldown tick: %d pooch(es) decremented.", decremented)
    return decremented


async def run_hourly_injury_persistence_check(rng_seed: Optional[int] = None) -> int:
    """
    Roll a constitution-based chance to decrement the persistence counter on each living
    pooch's injuries that have one. Injuries whose persistence reaches 0 are removed.

    Chance per injury instance = constitution / INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR.

    Parameters
    ----------
    rng_seed: int, optional
        Seed for reproducible rolls.

    Returns
    -------
    int
        Number of injury instances whose persistence was decremented.
    """

    import random as _random

    rng = _random.Random(rng_seed)
    constitution: dict[int, int] = {}
    decremented = 0
    for pooch_injury_id, pooch_id in await list_persistent_injury_instances():
        if pooch_id not in constitution:
            constitution[pooch_id] = await get_effective_stat(pooch_id, "constitution") or 0
        if rng.random() < constitution[pooch_id] / INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR:
            await reduce_pooch_injury_persistence(pooch_injury_id, 1)
            decremented += 1
    logger.info("Hourly injury persistence tick: %d injury instance(s) decremented.", decremented)
    return decremented


_SEVERITY_LEVEL: dict[str, int] = {severity: level for level, severity in enumerate(INJURY_SEVERITIES, start=1)}


def get_treatment_cost(severity: str) -> int:
    """Return the cost in dollars to treat one persistence point off an injury."""
    level = _SEVERITY_LEVEL.get(severity.lower(), 2)
    return VET_TREATMENT_BASE_COST + VET_TREATMENT_SEVERITY_COST_PER_LEVEL * level


def get_public_injury_label(pi: PoochInjury) -> str:
    """Return the injury name if it is visible, otherwise the symptom the owner sees."""
    if pi.visible:
        return pi.injury.name
    return pi.displayed_symptom or "a mysterious injury"


def is_injury_treated_today(pi: PoochInjury) -> bool:
    """Return True if the injury was already treated on the current UTC day."""
    if pi.last_treated_at is None:
        return False
    last = pi.last_treated_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last.date() == datetime.now(timezone.utc).date()


async def get_pooch_injury_instances(pooch_id: int) -> list[PoochInjury]:
    """
    Return the PoochInjury join records for the given pooch (including treatment state).
    The .injury relationship is eagerly loaded.
    """
    from src.database import list_pooch_injury_instances

    return await list_pooch_injury_instances(pooch_id)


def get_diagnose_injuries_cost() -> int:
    """
    Get diagnose injuries cost.

    Returns
    -------
    Any
        The result of calling `get_diagnose_injuries_cost`.
    """

    return VET_DIAGNOSE_INJURIES_COST


def get_diagnose_mutations_cost() -> int:
    """
    Get diagnose mutations cost.

    Returns
    -------
    Any
        The result of calling `get_diagnose_mutations_cost`.
    """

    return VET_DIAGNOSE_MUTATIONS_COST


async def treat_injury(
    owner_discord_id: int,
    pooch_injury_id: int,
) -> tuple[bool, str, int]:
    """
    Treat a PoochInjury. Charges the owner and applies treatment effects.

    Returns
    -------
    tuple[bool, str, int]
        (success, message, cost_charged)
    """
    pi = await get_pooch_injury_instance(pooch_injury_id)
    if pi is None:
        return False, "Injury not found.", 0
    if pi.pooch.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", 0

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", 0

    cost = get_treatment_cost(pi.injury.severity)

    if is_injury_treated_today(pi):
        return False, "This injury has already been treated today.", 0

    if owner.dollars < cost:
        return False, f"Not enough money. Treatment costs **${cost}**.", 0

    await give_money_to_owner(owner_discord_id, -cost)
    await treat_pooch_injury(pooch_injury_id)
    if pi.persistence is not None:
        await reduce_pooch_injury_persistence(pooch_injury_id, VET_TREATMENT_PERSISTENCE_REDUCTION)

    return True, f"Treatment successful. Charged **${cost}**.", cost


async def diagnose_injuries(
    owner_discord_id: int,
    pooch_id: int,
    rng_seed: Optional[int] = None,
) -> tuple[bool, str, list[str]]:
    """
    Attempt to reveal all invisible injuries on a pooch. Charges the owner $VET_DIAGNOSE_INJURIES_COST.

    Each invisible injury is revealed with probability equal to its ``reveal_chance``. Injuries that
    are already visible are skipped.

    Returns
    -------
    tuple[bool, str, list[str]]
        (success, error_message_if_failed, list_of_revealed_injury_names)
        On failure success is False and the message explains why. On success success is True,
        message is empty, and revealed_names lists every injury that was newly made visible.
    """
    import random as _random

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", []
    pooch_orm = await db_get_pooch_by_id(pooch_id)
    if pooch_orm is None:
        return False, "Pooch not found.", []
    if pooch_orm.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", []

    if owner.dollars < VET_DIAGNOSE_INJURIES_COST:
        return False, f"Not enough money. Diagnosis costs **${VET_DIAGNOSE_INJURIES_COST}**.", []

    rng = _random.Random(rng_seed)

    invisible_instances = await list_invisible_pooch_injury_instances(pooch_id)

    await give_money_to_owner(owner_discord_id, -VET_DIAGNOSE_INJURIES_COST)

    revealed: list[str] = []
    for pi in invisible_instances:
        reveal_chance = float(getattr(pi.injury, "reveal_chance", 1.0))
        if rng.random() < reveal_chance:
            await reveal_pooch_injury(pi.id)
            revealed.append(pi.injury.name)

    await set_pooch_vet_checked(pooch_id, checked=True)

    # Snapshot: record all currently visible injury IDs after diagnosis
    all_instances = await list_pooch_injury_instances(pooch_id)
    visible_injury_ids = [pi.injury_id for pi in all_instances if pi.visible]
    await create_pooch_snapshot(
        pooch_id=pooch_id,
        kind=SNAPSHOT_VET_INJURIES,
        description=f"{pooch_orm.name} had their injuries examined by a vet.",
        snapshot_at=datetime.now(timezone.utc),
        entity_ids=visible_injury_ids or None,
    )

    return True, "", revealed


async def diagnose_mutations(
    owner_discord_id: int,
    pooch_id: int,
    rng_seed: Optional[int] = None,
) -> tuple[bool, str, list[str]]:
    """
    Attempt to reveal all invisible mutations on a pooch. Charges the owner $VET_DIAGNOSE_MUTATIONS_COST.

    Each invisible mutation is revealed with probability equal to its ``reveal_chance``. Mutations that
    are already visible are skipped.

    Returns
    -------
    tuple[bool, str, list[str]]
        (success, error_message_if_failed, list_of_revealed_mutation_names)
        On failure success is False and the message explains why. On success success is True,
        message is empty, and revealed_names lists every mutation that was newly made visible.
    """
    import random as _random

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", []
    pooch_orm = await db_get_pooch_by_id(pooch_id)
    if pooch_orm is None:
        return False, "Pooch not found.", []
    if pooch_orm.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", []

    if owner.dollars < VET_DIAGNOSE_MUTATIONS_COST:
        return False, f"Not enough money. Diagnosis costs **${VET_DIAGNOSE_MUTATIONS_COST}**.", []

    rng = _random.Random(rng_seed)

    invisible_instances = await list_invisible_pooch_mutation_instances(pooch_id)

    await give_money_to_owner(owner_discord_id, -VET_DIAGNOSE_MUTATIONS_COST)

    revealed: list[str] = []
    for pm in invisible_instances:
        reveal_chance = float(getattr(pm.mutation, "reveal_chance", 1.0))
        if rng.random() < reveal_chance:
            await reveal_pooch_mutation(pm.pooch_id, pm.mutation_id)
            revealed.append(pm.mutation.name)

    await set_pooch_vet_checked(pooch_id, checked=True)

    # Snapshot: record all currently visible mutation IDs after diagnosis
    all_mut_instances = await list_pooch_mutation_instances(pooch_id)
    visible_mutation_ids = [pm.mutation_id for pm in all_mut_instances if pm.visible]
    await create_pooch_snapshot(
        pooch_id=pooch_id,
        kind=SNAPSHOT_VET_MUTATIONS,
        description=f"{pooch_orm.name} had their mutations examined by a vet.",
        snapshot_at=datetime.now(timezone.utc),
        entity_ids=visible_mutation_ids or None,
    )

    return True, "", revealed


async def rename_pooch(pooch_id: int, name: str) -> bool:
    """
    Rename the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to rename.

    name: str
        The new name to give the pooch.

    max_name_length: int
        Maximum allowed name length.

    Returns
    -------
    bool
        True if renamed, False if the name is too long.

    Raises
    ------
    PoochNotFound
        When a Pooch with `pooch_id` is not found.
    """

    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        return False

    pooch = await db_rename_pooch(pooch_id, name)
    if pooch is None:
        raise PoochNotFound(pooch_id)
    return True


MEDICAL_EXAM_COST = 25


def _rate_stat(value: int) -> str:
    if value <= 4:
        return "Significantly Below Average"
    if value <= 7:
        return "Below Average"
    if value <= 9:
        return "Slightly Below Average"
    if value == 10:
        return "Average"
    if value <= 12:
        return "Slightly Above Average"
    if value <= 15:
        return "Above Average"
    return "Significantly Above Average"


async def medical_exam(owner_discord_id: int, pooch: "Pooch") -> tuple[bool, str, dict]:
    """
    Perform a medical exam on a pooch. Charges the owner $MEDICAL_EXAM_COST.

    Returns
    -------
    tuple[bool, str, dict]
        (success, error_message, stats_report)
        stats_report maps stat name → display string.
    """
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", {}
    if pooch.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", {}
    if owner.dollars < MEDICAL_EXAM_COST:
        return False, f"Not enough money. A medical exam costs **${MEDICAL_EXAM_COST}**.", {}

    await give_money_to_owner(owner_discord_id, -MEDICAL_EXAM_COST)

    # The exam describes the pooch as it really is: breeds, conditions, hunger etc. all count
    stats = await get_effective_stats(pooch.id) or {}
    report = {
        "Strength": _rate_stat(stats.get("strength", pooch.strength)),
        "Cuteness": _rate_stat(stats.get("cuteness", pooch.cuteness)),
        "Fluffiness": _rate_stat(stats.get("fluffiness", pooch.fluffiness)),
        "Intelligence": _rate_stat(stats.get("intelligence", pooch.intelligence)),
        "Dexterity": _rate_stat(stats.get("dexterity", pooch.dexterity)),
        "Fertility": _rate_stat(stats.get("fertility", pooch.fertility)),
        "Aggressiveness": _rate_stat(stats.get("aggressiveness", pooch.aggressiveness)),
        "Constitution": _rate_stat(stats.get("constitution", pooch.constitution)),
        "Size Class": str(stats.get("size", pooch.size)),
    }

    stats_lines = "\n".join(f"{k}: {v}" for k, v in report.items())
    await create_pooch_snapshot(
        pooch_id=pooch.id,
        kind=SNAPSHOT_MEDICAL_EXAM,
        description=f"{pooch.name} received a medical exam.\n{stats_lines}",
    )

    return True, "", report


async def mark_pooch_vet_checked(pooch_id: int) -> None:
    """Mark a pooch as vet-checked."""
    await set_pooch_vet_checked(pooch_id, checked=True)


async def list_snapshots_for_pooch(pooch_id: int) -> list:
    """Return all timeline snapshots for a pooch, oldest first."""
    return await db_list_pooch_snapshots(pooch_id)


def _vet_visit_lookup(kind: str):
    """The catalog lookup for the conditions a vet visit snapshot records, or None for other snapshots."""
    return {
        SNAPSHOT_VET_INJURIES: get_injury_by_id,
        SNAPSHOT_VET_MUTATIONS: get_mutation_by_id,
        SNAPSHOT_VET_DISEASES: get_disease_by_id,
    }.get(kind)


def _exam_ratings(description: str) -> dict[str, str]:
    """Read the ``Stat: rating`` lines a medical exam writes under its first line (a Detailed Workup has none)."""
    ratings = {}
    for line in description.splitlines()[1:]:
        stat, sep, rating = line.partition(": ")
        if sep:
            ratings[stat] = rating
    return ratings


async def get_latest_vet_results(pooch_id: int) -> dict:
    """
    The latest medical exam and disease diagnosis on record for a pooch, for its owner's pooch page.

    Both come from the pooch's timeline, so they show the pooch as it was at that visit.

    Returns
    -------
    dict
        ``{"medical_exam": {"at": datetime, "ratings": {stat: rating}} | None,
        "disease_diagnosis": {"at": datetime, "diseases": [name, ...]} | None}``
    """

    results: dict = {"medical_exam": None, "disease_diagnosis": None}
    for snap in reversed(await db_list_pooch_snapshots(pooch_id)):
        if results["medical_exam"] is None and snap.kind == SNAPSHOT_MEDICAL_EXAM:
            ratings = _exam_ratings(snap.description)
            if ratings:
                results["medical_exam"] = {"at": snap.snapshot_at, "ratings": ratings}
        elif results["disease_diagnosis"] is None and snap.kind == SNAPSHOT_VET_DISEASES:
            diseases = [await get_disease_by_id(disease_id) for disease_id in snap.entity_ids or []]
            results["disease_diagnosis"] = {
                "at": snap.snapshot_at,
                "diseases": [disease.name for disease in diseases if disease],
            }
        if all(results.values()):
            break
    return results


async def get_pooch_timeline(pooch_id: int) -> list[PoochTimelineEntry]:
    """
    Return a pooch's timeline, oldest first, with vet-visit injury/mutation IDs resolved to names.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch.

    Returns
    -------
    list[PoochTimelineEntry]
        One entry per snapshot. ``entity_names`` is set only for vet visits that recorded IDs.
    """

    entries: list[PoochTimelineEntry] = []
    for snap in await db_list_pooch_snapshots(pooch_id):
        entity_names: Optional[list[str]] = None
        lookup = _vet_visit_lookup(snap.kind)
        if snap.entity_ids and lookup is not None:
            entity_names = []
            for entity_id in snap.entity_ids:
                entity = await lookup(entity_id)
                if entity:
                    entity_names.append(entity.name)
        entries.append(
            PoochTimelineEntry(
                kind=snap.kind,
                description=snap.description,
                snapshot_at=snap.snapshot_at,
                entity_names=entity_names,
            )
        )
    return entries


def _public_source_label(kind: str, instance) -> str:
    """Name a condition in a Detailed Workup: its real name once diagnosed, otherwise only its symptom."""
    catalog = getattr(instance, kind, instance)
    if getattr(instance, "visible", True):
        return catalog.name
    fallback = {
        "mutation": "an undiagnosed mutation",
        "injury": "a mysterious injury",
        "disease": "a mysterious illness",
    }
    return getattr(instance, "displayed_symptom", None) or fallback[kind]


DETAILED_WORKUP_COST = 75


async def detailed_workup(owner_discord_id: int, pooch_id: int) -> tuple[bool, str, dict]:
    """
    Pricier vet procedure that returns the exact base/effective values for
    every stat plus a per-source breakdown. Persists the result as a snapshot
    so the player can review their pooch's history.

    Hidden mutations, injuries and diseases are listed under their displayed symptom, never their name.
    """
    from .utils.obfuscation import stat_label

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", {}
    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        return False, "Pooch not found.", {}
    if pooch.owner_discord_id != owner_discord_id:
        return False, "That's not your pooch.", {}
    if owner.dollars < DETAILED_WORKUP_COST:
        return False, f"Not enough money. A detailed workup costs **${DETAILED_WORKUP_COST}**.", {}

    await give_money_to_owner(owner_discord_id, -DETAILED_WORKUP_COST)

    breakdown = await get_effective_stats(pooch_id, return_breakdown=True, label=_public_source_label)

    # Format with labels per stat for the UI.
    report = {}
    for stat, info in breakdown.items():
        if stat == "base_health":
            # Exact health is never shown to players.
            continue
        eff = int(round(info["effective"]))
        base = int(round(info["base"]))
        label = stat_label(eff)
        report[stat] = {
            "base": base,
            "effective": eff,
            "label": label,
            "sources": info["sources"],
        }

    # Persist as a snapshot.
    await create_pooch_snapshot(
        pooch_id=pooch.id,
        kind=SNAPSHOT_MEDICAL_EXAM,
        description=f"{pooch.name} received a Detailed Workup.",
    )

    return True, "", report
