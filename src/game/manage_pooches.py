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
        father, mother = await get_pooch_parents(pid)
        for parent in (father, mother):
            if parent is None:
                continue
            edges.add((parent.id, pid))
            prev_gen = node_generation.get(parent.id, -1)
            await _add_node(parent, generation)
            # Only recurse if this is a new node or placed at a higher generation
            if generation > prev_gen:
                await _fetch_ancestors(parent.id, depth - 1, generation + 1)

    async def _fetch_descendants(pid: int, depth: int, generation: int):
        if depth <= 0:
            return
        children = await list_pooch_children(pid)
        for child in children:
            edges.add((pid, child.id))
            prev_gen = node_generation.get(child.id, 999)
            await _add_node(child, generation)
            # Only recurse if this is a new node or placed at a lower generation
            if generation < prev_gen:
                await _fetch_descendants(child.id, depth - 1, generation - 1)

    # Start with the root pooch
    root_orm = await db_get_pooch_by_id(pooch_id)
    if root_orm is None:
        raise PoochNotFound(f"Pooch {pooch_id} not found.")

    await _add_node(root_orm, 0)

    # Fetch ancestors (positive generations) and descendants (negative generations)
    await _fetch_ancestors(pooch_id, ancestor_depth, 1)
    await _fetch_descendants(pooch_id, descendant_depth, -1)

    # Attach generation to each node
    for pid, node in nodes.items():
        node["generation"] = node_generation[pid]

    return {
        "root_id": pooch_id,
        "nodes": list(nodes.values()),
        "edges": [{"source": s, "target": t} for s, t in edges],
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
