from typing import Optional

from sqlalchemy import and_, func, literal, or_, select, union

from .models import (
    HealthImpactWeight,
    Kennel,
    KennelPooch,
    Mutation,
    Owner,
    OwnerServer,
    Pooch,
    PoochMutation,
    PoochParentage,
    Server,
    Vendor,
)
from .session import session_scope


async def get_kennel_by_id(kennel_id: int) -> Optional[Kennel]:
    """
    Fetch the kennel with the given ID.

    Parameters
    ----------
    kennel_id: int
        The ID of the kennel to fetch.

    Returns
    -------
    Kennel, optional
        The Kennel ORM object with the given ID, or None if no kennel with the given ID was found.
    """

    async with session_scope() as session:
        response = await session.execute(select(Kennel).where(Kennel.id == kennel_id))

    return response.scalar_one_or_none()


async def get_mutation_by_id(mutation_id: int) -> Optional[Mutation]:
    """
    Fetch a mutation by its ID.

    Parameters
    ----------
    mutation_id: int
        The ID of the mutation to fetch.

    Returns
    -------
    Mutation, optional
        The Mutation ORM object, or None if no mutation with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Mutation).where(Mutation.id == mutation_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_mutation_health_impact(mutation_id: int) -> Optional[int]:
    """
    Get the health impact for the mutation with the given ID as an integer.

    Parameters
    ----------
    mutation_id: int
        The ID of the mutation to get the numerical health impact of.

    Returns
    -------
    int, optional
        The health impact of the given mutation, or None if the mutation wasn't found.
    """

    async with session_scope() as session:
        query = (
            select(HealthImpactWeight.weight)
            .join(Mutation, Mutation.health_impact == HealthImpactWeight.health_impact)
            .where(Mutation.id == mutation_id)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_by_discord_id(owner_discord_id: int) -> Optional[Owner]:
    """
    Fetch an owner by their Discord ID.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch.

    Returns
    -------
    Owner, optional
        The Owner ORM object, or None if no owner with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Owner).where(Owner.discord_id == owner_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_owner_server(server_discord_id: int, owner_discord_id: int) -> Optional[OwnerServer]:
    """
    Get the owner-server relationship with the given server and owner Discord IDs.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server in the owner-server relationship.

    owner_discord_id: int
        The Discord ID of the owner in the owner-server relationship.

    Returns
    -------
    OwnerServer, optional
        The OwnerServer ORM relationship object with the given ID pair, or None if it doesn't exist.
    """

    async with session_scope() as session:
        query = select(OwnerServer).where(
            and_(OwnerServer.server_discord_id == server_discord_id, OwnerServer.owner_discord_id == owner_discord_id)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_pooch_by_id(pooch_id: int) -> Optional[Pooch]:
    """
    Fetch the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch.

    Returns
    -------
    Option[Pooch]
        The Pooch ORM object with the given ID, or None if no Pooch with that ID exists.
    """

    async with session_scope() as session:
        query = select(Pooch).where(Pooch.id == pooch_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_pooch_health(pooch_id: int) -> Optional[int]:
    """
    Get the current health of the given pooch, taking into account age and mutations.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the health of.

    Returns
    -------
    int, optional
        The current health of the pooch, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = (
            select(Pooch.base_health - Pooch.health_loss_age + func.coalesce(func.sum(HealthImpactWeight.weight), 0))
            .outerjoin(PoochMutation, PoochMutation.pooch_id == Pooch.id)
            .outerjoin(Mutation, Mutation.id == PoochMutation.mutation_id)
            .outerjoin(HealthImpactWeight, HealthImpactWeight.health_impact == Mutation.health_impact)
            .where(Pooch.id == pooch_id)
            .group_by(Pooch.id, Pooch.base_health, Pooch.health_loss_age)
        )
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_pooch_kennel(pooch_id: int) -> Optional[Kennel]:
    """
    Fetch the kennel the pooch with the given ID belongs to.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch the kennel of.

    Returns
    -------
    Kennel, optional
        The Kennel the pooch with the given ID belongs to, or None if it doesn't belong to a kennel.
    """

    async with session_scope() as session:
        query = (
            select(Kennel)
            .join(KennelPooch, KennelPooch.kennel_id == Kennel.id)
            .join(Owner, Owner.discord_id == Kennel.owner_discord_id)
            .where(KennelPooch.pooch_id == pooch_id)
            .limit(1)
        )
        response = await session.execute(query)

    kennel = response.scalar_one_or_none()
    return kennel


async def get_pooch_parents(pooch_id: int) -> tuple[Optional[Pooch], Optional[Pooch]]:
    """
    Fetch the parents of the pooch with the given ID.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to fetch the parents of.

    Returns
    -------
    tuple[Optional[Pooch], Optional[Pooch]]
        A tuple of Pooch ORM objects in the form (father, mother).
    """

    async with session_scope() as session:
        parentage = (
            await session.execute(select(PoochParentage).where(PoochParentage.child_id == pooch_id))
        ).scalar_one_or_none()

    if not parentage:
        return (None, None)

    father = await get_pooch_by_id(parentage.father_id)
    mother = await get_pooch_by_id(parentage.mother_id)

    return (father, mother)


async def get_pooch_virginity_status(pooch_id: int) -> Optional[bool]:
    """
    Get whether the pooch with the given ID is a virgin or not.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the virginity status of.

    Returns
    -------
    bool, optional
        Whether the pooch is a virgin or not, or None if the pooch wasn't found.
    """

    async with session_scope() as session:
        query = select(Pooch.virgin).where(Pooch.id == pooch_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_server_by_discord_id(server_discord_id: int) -> Optional[Server]:
    """
    Fetch a server by its Discord ID.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to fetch.

    Returns
    -------
    Server, optional
        The Server ORM object, or None if no server with the given ID exists.
    """

    async with session_scope() as session:
        query = select(Server).where(Server.discord_id == server_discord_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_vendor_by_id(vendor_id: int) -> Optional[Vendor]:
    """
    Fetch the vendor with the given ID.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to fetch.

    Returns
    -------
    Vendor, optional
        The Vendor ORM object with the given ID, or None if no vendor with that ID was found.
    """

    async with session_scope() as session:
        response = await session.execute(select(Vendor).where(Vendor.id == vendor_id))

    vendor = response.scalar_one_or_none()
    return vendor


async def get_vendor_server(vendor_id: int) -> Optional[Server]:
    """
    Get the server the vendor with the given ID belongs to.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to get the server for.

    Returns
    -------
    Server, optional
        The Server ORM object representing the server the vendor belongs to.
    """

    async with session_scope() as session:
        query = select(Server).join(Vendor, Vendor.server_discord_id == Server.discord_id).where(Vendor.id == vendor_id)
        response = await session.execute(query)

    return response.scalar_one_or_none()


async def get_parentage_maps(
    root_id: int, ancestor_depth: int, descendant_depth: int,
) -> tuple[dict[int, tuple[int | None, int | None]], dict[int, list[int]]]:
    """
    Load parentage rows reachable from *root_id* within the given depth limits
    using recursive CTEs (1 query).

    Parameters
    ----------
    root_id: int
        The ID of the root pooch to start traversal from.
    ancestor_depth: int
        How many generations upward to traverse.
    descendant_depth: int
        How many generations downward to traverse.

    Returns
    -------
    tuple[dict, dict]
        (parents_of, children_of) where:
        parents_of[child_id] = (father_id, mother_id)
        children_of[parent_id] = [child_id, ...]
    """
    # Ancestor recursive CTE
    ancestor_base = (
        select(
            PoochParentage.child_id,
            PoochParentage.father_id,
            PoochParentage.mother_id,
            literal(0).label("depth"),
        )
        .where(PoochParentage.child_id == root_id)
    )
    ancestor_cte = ancestor_base.cte("ancestor_rows", recursive=True)

    ancestor_recursive = (
        select(
            PoochParentage.child_id,
            PoochParentage.father_id,
            PoochParentage.mother_id,
            (ancestor_cte.c.depth + 1).label("depth"),
        )
        .join(
            ancestor_cte,
            or_(
                PoochParentage.child_id == ancestor_cte.c.father_id,
                PoochParentage.child_id == ancestor_cte.c.mother_id,
            ),
        )
        .where(ancestor_cte.c.depth < ancestor_depth)
    )
    ancestor_cte = ancestor_cte.union_all(ancestor_recursive)

    # Descendant recursive CTE
    descendant_base = (
        select(
            PoochParentage.child_id,
            PoochParentage.father_id,
            PoochParentage.mother_id,
            literal(1).label("depth"),
        )
        .where(
            or_(
                PoochParentage.father_id == root_id,
                PoochParentage.mother_id == root_id,
            )
        )
    )
    descendant_cte = descendant_base.cte("descendant_rows", recursive=True)

    descendant_recursive = (
        select(
            PoochParentage.child_id,
            PoochParentage.father_id,
            PoochParentage.mother_id,
            (descendant_cte.c.depth + 1).label("depth"),
        )
        .join(
            descendant_cte,
            or_(
                PoochParentage.father_id == descendant_cte.c.child_id,
                PoochParentage.mother_id == descendant_cte.c.child_id,
            ),
        )
        .where(descendant_cte.c.depth < descendant_depth)
    )
    descendant_cte = descendant_cte.union_all(descendant_recursive)

    # Sibling query: rows sharing the same parents as root
    PP2 = PoochParentage.__table__.alias("sibling_pp")
    sibling_query = (
        select(
            PP2.c.child_id,
            PP2.c.father_id,
            PP2.c.mother_id,
        )
        .where(
            PP2.c.father_id == select(PoochParentage.father_id).where(
                PoochParentage.child_id == root_id
            ).correlate(None).scalar_subquery(),
            PP2.c.mother_id == select(PoochParentage.mother_id).where(
                PoochParentage.child_id == root_id
            ).correlate(None).scalar_subquery(),
        )
    )

    # Combine all three into a single query
    combined = union(
        select(
            ancestor_cte.c.child_id,
            ancestor_cte.c.father_id,
            ancestor_cte.c.mother_id,
        ),
        select(
            descendant_cte.c.child_id,
            descendant_cte.c.father_id,
            descendant_cte.c.mother_id,
        ),
        sibling_query,
    )

    parents_of: dict[int, tuple[int | None, int | None]] = {}
    children_of: dict[int, list[int]] = {}

    async with session_scope() as session:
        result = await session.execute(combined)
        rows = result.all()

    for row in rows:
        cid, fid, mid = row[0], row[1], row[2]
        parents_of[cid] = (fid, mid)
        if fid is not None:
            children_of.setdefault(fid, []).append(cid)
        if mid is not None:
            children_of.setdefault(mid, []).append(cid)

    for kids in children_of.values():
        kids.sort()

    return parents_of, children_of
