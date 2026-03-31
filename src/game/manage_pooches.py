from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from src.database import (
    get_owner_by_discord_id,
    get_parentage_maps,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_pooch_parents,
    give_money_to_owner,
    list_pooch_children,
    list_pooch_siblings,
    list_pooches_with_health,
    reduce_pooch_injury_persistence,
)
from src.database import rename_pooch as db_rename_pooch
from src.database import (
    reveal_pooch_injury,
    reveal_pooch_mutation,
    tick_hourly_breeding_cooldowns,
    tick_hourly_injury_persistence,
    treat_pooch_injury,
)
from src.database.models import PoochInjury
from src.logger import get_logger

from .constants import (
    BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR,
    INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR,
    MAX_NAME_LENGTH,
    VET_DIAGNOSE_INJURIES_COST,
    VET_DIAGNOSE_MUTATIONS_COST,
    VET_TREATMENT_BASE_COST,
    VET_TREATMENT_PERSISTENCE_REDUCTION,
    VET_TREATMENT_SEVERITY_COST_PER_LEVEL,
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


_SEVERITY_LEVEL: dict[str, int] = {
    "trivial": 1,
    "minor": 2,
    "moderate": 3,
    "major": 4,
    "critical": 5,
    "remarkable": 6,
    "catastrophic": 7,
}


def get_treatment_cost(severity: str) -> int:
    """Return the cost in dollars to treat one persistence point off an injury."""
    level = _SEVERITY_LEVEL.get(severity.lower(), 2)
    return VET_TREATMENT_BASE_COST + VET_TREATMENT_SEVERITY_COST_PER_LEVEL * level


async def get_pooch_injury_instances(pooch_id: int) -> list[PoochInjury]:
    """
    Return the PoochInjury join records for the given pooch (including treatment state).
    The .injury relationship is eagerly loaded.
    """
    from src.database import list_pooch_injury_instances

    return await list_pooch_injury_instances(pooch_id)


def get_diagnose_injuries_cost() -> int:
    return VET_DIAGNOSE_INJURIES_COST


def get_diagnose_mutations_cost() -> int:
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
    # Load the specific instance with eager injury relationship
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.database.models import PoochInjury as PoochInjuryORM
    from src.database.session import session_scope

    injury_severity = None
    persistence = None
    last_treated_at = None

    async with session_scope() as session:
        query = (
            select(PoochInjuryORM)
            .options(selectinload(PoochInjuryORM.injury))
            .where(PoochInjuryORM.id == pooch_injury_id)
        )
        result = await session.execute(query)
        pi = result.scalar_one_or_none()
        if pi is None:
            return False, "Injury not found.", 0
        injury_severity = pi.injury.severity
        persistence = pi.persistence
        last_treated_at = pi.last_treated_at

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", 0

    cost = get_treatment_cost(injury_severity)

    # Check if already treated today
    if last_treated_at is not None:
        now = datetime.now(timezone.utc)
        last = last_treated_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last.date() == now.date():
            return False, "This injury has already been treated today.", 0

    if owner.dollars < cost:
        return False, f"Not enough money. Treatment costs **${cost}**.", 0

    await give_money_to_owner(owner_discord_id, -cost)
    await treat_pooch_injury(pooch_injury_id)
    if persistence is not None:
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

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.database.models import PoochInjury as PoochInjuryORM
    from src.database.session import session_scope

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", []

    if owner.dollars < VET_DIAGNOSE_INJURIES_COST:
        return False, f"Not enough money. Diagnosis costs **${VET_DIAGNOSE_INJURIES_COST}**.", []

    rng = _random.Random(rng_seed)

    async with session_scope() as session:
        query = (
            select(PoochInjuryORM)
            .options(selectinload(PoochInjuryORM.injury))
            .where(PoochInjuryORM.pooch_id == pooch_id, PoochInjuryORM.visible.is_(False))
        )
        result = await session.execute(query)
        invisible_instances = list(result.scalars().all())

    await give_money_to_owner(owner_discord_id, -VET_DIAGNOSE_INJURIES_COST)

    revealed: list[str] = []
    for pi in invisible_instances:
        reveal_chance = float(getattr(pi.injury, "reveal_chance", 1.0))
        if rng.random() < reveal_chance:
            await reveal_pooch_injury(pi.id)
            revealed.append(pi.injury.name)

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

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.database.models import PoochMutation as PoochMutationORM
    from src.database.session import session_scope

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found.", []

    if owner.dollars < VET_DIAGNOSE_MUTATIONS_COST:
        return False, f"Not enough money. Diagnosis costs **${VET_DIAGNOSE_MUTATIONS_COST}**.", []

    rng = _random.Random(rng_seed)

    async with session_scope() as session:
        query = (
            select(PoochMutationORM)
            .options(selectinload(PoochMutationORM.mutation))
            .where(PoochMutationORM.pooch_id == pooch_id, PoochMutationORM.visible.is_(False))
        )
        result = await session.execute(query)
        invisible_instances = list(result.scalars().all())

    await give_money_to_owner(owner_discord_id, -VET_DIAGNOSE_MUTATIONS_COST)

    revealed: list[str] = []
    for pm in invisible_instances:
        reveal_chance = float(getattr(pm.mutation, "reveal_chance", 1.0))
        if rng.random() < reveal_chance:
            await reveal_pooch_mutation(pm.pooch_id, pm.mutation_id)
            revealed.append(pm.mutation.name)

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
