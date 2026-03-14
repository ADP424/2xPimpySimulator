from database import get_pooch_by_id as db_get_pooch_by_id
from database import (
    get_pooch_parents,
    list_pooch_children,
    list_pooch_siblings,
)
from database.models import PoochParentage
from database.models import Pooch as PoochORM
from database.session import session_scope
from database.update import rename_pooch as db_rename_pooch
from sqlalchemy import func, select

from .constants import MAX_NAME_LENGTH
from .exceptions.pooch_not_found import PoochNotFound
from .models import Pooch, to_pooch


async def _load_parentage_maps(
    root_id: int, ancestor_depth: int, descendant_depth: int,
) -> tuple[dict[int, tuple[int | None, int | None]], dict[int, list[int]]]:
    """Load only the parentage rows reachable from *root_id* within the given
    depth limits using recursive CTEs (1 query).

    Returns (parents_of, children_of) where:
        parents_of[child_id] = (father_id, mother_id)
        children_of[parent_id] = [child_id, ...]
    """
    from sqlalchemy import text

    sql = text("""
        WITH RECURSIVE
        ancestor_rows(child_id, father_id, mother_id, depth) AS (
            SELECT pp.child_id, pp.father_id, pp.mother_id, 0
            FROM pooch_parentage pp WHERE pp.child_id = :root_id
            UNION ALL
            SELECT pp.child_id, pp.father_id, pp.mother_id, ar.depth + 1
            FROM pooch_parentage pp
            JOIN ancestor_rows ar
              ON pp.child_id = ar.father_id OR pp.child_id = ar.mother_id
            WHERE ar.depth < :anc_depth
        ),
        descendant_rows(child_id, father_id, mother_id, depth) AS (
            SELECT pp.child_id, pp.father_id, pp.mother_id, 1
            FROM pooch_parentage pp
            WHERE pp.father_id = :root_id OR pp.mother_id = :root_id
            UNION ALL
            SELECT pp.child_id, pp.father_id, pp.mother_id, dr.depth + 1
            FROM pooch_parentage pp
            JOIN descendant_rows dr
              ON pp.father_id = dr.child_id OR pp.mother_id = dr.child_id
            WHERE dr.depth < :desc_depth
        )
        SELECT DISTINCT child_id, father_id, mother_id FROM (
            SELECT child_id, father_id, mother_id FROM ancestor_rows
            UNION
            SELECT child_id, father_id, mother_id FROM descendant_rows
        ) combined
    """)

    parents_of: dict[int, tuple[int | None, int | None]] = {}
    children_of: dict[int, list[int]] = {}

    async with session_scope() as session:
        result = await session.execute(
            sql, {"root_id": root_id, "anc_depth": ancestor_depth, "desc_depth": descendant_depth}
        )
        rows = result.all()

    for row in rows:
        cid, fid, mid = row[0], row[1], row[2]
        parents_of[cid] = (fid, mid)
        if fid is not None:
            children_of.setdefault(fid, []).append(cid)
        if mid is not None:
            children_of.setdefault(mid, []).append(cid)

    # Sort children by ID (matches creation order since IDs are autoincrement)
    for kids in children_of.values():
        kids.sort()

    return parents_of, children_of


async def _batch_fetch_pooches(pooch_ids: set[int]) -> dict[int, dict]:
    """Batch-fetch pooch data + computed health in a single joined query.

    Returns dict of {pooch_id: {id, name, sex, alive, age, health}}.
    """
    if not pooch_ids:
        return {}

    from database.models import HealthImpactWeight, Mutation, PoochMutation

    async with session_scope() as session:
        query = (
            select(
                PoochORM.id,
                PoochORM.name,
                PoochORM.sex,
                PoochORM.alive,
                PoochORM.age,
                (PoochORM.base_health - PoochORM.health_loss_age + func.coalesce(func.sum(HealthImpactWeight.weight), 0)).label("health"),
            )
            .outerjoin(PoochMutation, PoochMutation.pooch_id == PoochORM.id)
            .outerjoin(Mutation, Mutation.id == PoochMutation.mutation_id)
            .outerjoin(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(PoochORM.id.in_(pooch_ids))
            .group_by(PoochORM.id, PoochORM.name, PoochORM.sex, PoochORM.alive, PoochORM.age, PoochORM.base_health, PoochORM.health_loss_age)
        )
        rows = (await session.execute(query)).all()

    return {
        row[0]: {"id": row[0], "name": row[1], "sex": row[2], "alive": row[3], "age": row[4], "health": int(row[5])}
        for row in rows
    }


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
    parents_of, children_of = await _load_parentage_maps(pooch_id, ancestor_depth, descendant_depth)

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
    pooches = await _batch_fetch_pooches(needed_ids)

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
        nodes.append({
            "id": p["id"],
            "name": p["name"],
            "sex": p["sex"],
            "alive": p["alive"],
            "age": p["age"],
            "status": _pooch_status(p["alive"], p["age"], p["health"]),
            "generation": node_generation.get(pid, 0),
        })

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
        couples.append({
            "parents": [a_id, b_id],
            "children": list(children_ids),
            "incest_level": round(incest_level, 4),
        })

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
