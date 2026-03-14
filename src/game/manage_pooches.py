from database import get_pooch_by_id as db_get_pooch_by_id
from database import (
    get_pooch_parents,
    list_pooch_children,
    list_pooch_siblings,
)
from database.update import rename_pooch as db_rename_pooch

from .constants import MAX_NAME_LENGTH
from .exceptions.pooch_not_found import PoochNotFound
from .models import Pooch, to_pooch


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
    nodes: dict[int, dict] = {}
    edges: set[tuple[int, int]] = set()
    # Track the maximum generation (distance from root) for each node
    node_generation: dict[int, int] = {}
    # Track the max remaining depth each node has been explored with
    ancestor_explored: dict[int, int] = {}
    descendant_explored: dict[int, int] = {}

    async def _add_node(orm_pooch, generation: int):
        pid = orm_pooch.id
        if pid not in nodes:
            game_pooch = await to_pooch(orm_pooch)
            nodes[pid] = {
                "id": pid,
                "name": game_pooch.name,
                "sex": game_pooch.sex,
                "alive": game_pooch.alive,
                "age": game_pooch.age,
                "status": game_pooch.status,
            }
        # Place node at the highest (most ancestral) generation it appears at
        if pid not in node_generation or generation > node_generation[pid]:
            node_generation[pid] = generation

    async def _fetch_ancestors(pid: int, depth: int, generation: int):
        if depth <= 0:
            return
        # Skip if already explored with at least this much depth
        if ancestor_explored.get(pid, -1) >= depth:
            return
        ancestor_explored[pid] = depth

        father, mother = await get_pooch_parents(pid)
        for parent in (father, mother):
            if parent is None:
                continue
            edges.add((parent.id, pid))
            await _add_node(parent, generation)
            await _fetch_ancestors(parent.id, depth - 1, generation + 1)

    async def _fetch_descendants(pid: int, depth: int, generation: int):
        if depth <= 0:
            return
        # Skip if already explored with at least this much depth
        if descendant_explored.get(pid, -1) >= depth:
            return
        descendant_explored[pid] = depth

        children = await list_pooch_children(pid)
        for child in children:
            edges.add((pid, child.id))
            await _add_node(child, generation)

            # Also fetch and add the child's other parent (mate of pid)
            father, mother = await get_pooch_parents(child.id)
            for parent in (father, mother):
                if parent is not None and parent.id != pid:
                    if parent.id in node_generation:
                        await _add_node(parent, node_generation[parent.id])
                    else:
                        mate_gen = node_generation.get(pid, 0)
                        await _add_node(parent, mate_gen)
                    edges.add((parent.id, child.id))

            await _fetch_descendants(child.id, depth - 1, generation - 1)

    # Start with the root pooch
    root_orm = await db_get_pooch_by_id(pooch_id)
    if root_orm is None:
        raise PoochNotFound(f"Pooch {pooch_id} not found.")

    await _add_node(root_orm, 0)

    # Fetch ancestors (positive generations) and descendants (negative generations)
    await _fetch_ancestors(pooch_id, ancestor_depth, 1)
    await _fetch_descendants(pooch_id, descendant_depth, -1)

    # Fetch siblings of the root pooch (same generation as root)
    siblings_orm = await list_pooch_siblings(pooch_id)
    for sibling in siblings_orm:
        await _add_node(sibling, 0)
        # Add edges from parents to this sibling (parents are already in the tree)
        father, mother = await get_pooch_parents(sibling.id)
        if father:
            edges.add((father.id, sibling.id))
        if mother:
            edges.add((mother.id, sibling.id))

    # Ensure every child is strictly below ALL its parents.
    # When cross-generation mating occurs, a child may have been placed at the
    # same generation as one parent.  Iteratively push children down until the
    # constraint holds for every edge.
    changed = True
    while changed:
        changed = False
        for source, target in edges:
            parent_gen = node_generation.get(source, 0)
            child_gen = node_generation.get(target, 0)
            if child_gen >= parent_gen:
                node_generation[target] = parent_gen - 1
                changed = True

    # Attach generation to each node
    for pid, node in nodes.items():
        node["generation"] = node_generation[pid]

    # Compute incest levels for each mating pair
    from .breeding import calculate_incest_level

    # Find unique parent pairs from edges
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
        "nodes": list(nodes.values()),
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
