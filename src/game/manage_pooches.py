from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.database import (
    get_parentage_maps,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_pooch_parents,
    list_pooch_children,
    list_pooch_siblings,
    list_pooches_with_health,
)
from src.database import rename_pooch as db_rename_pooch
from src.database import (
    tick_hourly_breeding_cooldowns,
    tick_hourly_injury_persistence,
)
from src.logger import get_logger

from .constants import (
    BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR,
    INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR,
    MAX_NAME_LENGTH,
)
from .exceptions import PoochNotFound
from .models import to_pooch

logger = get_logger("game/manage_pooches")

if TYPE_CHECKING:
    from .models import Pooch


def _pooch_status(alive: bool, age: int, health: int) -> str:
    if not alive:
        return "dead"
    elif age >= 12:
        return "old"
    elif health <= 3:
        return "sick"
    return "healthy"


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
                "status": _pooch_status(p["alive"], p["age"], p["health"]),
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

    decremented = await tick_hourly_breeding_cooldowns(
        fertility_divisor=BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR,
        rng_seed=rng_seed,
    )
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

    decremented = await tick_hourly_injury_persistence(
        constitution_divisor=INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR,
        rng_seed=rng_seed,
    )
    logger.info("Hourly injury persistence tick: %d injury instance(s) decremented.", decremented)
    return decremented


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
