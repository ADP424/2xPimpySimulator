"""
Upgrade a live database from web-bot-parity to the lots-of-changes merge without losing players.

Safe to run more than once: each step only adds what is missing or corrects data to match the models and resources.
Nothing is ever deleted.

1. Schema: create missing tables (``items``, ``owner_items``), then add every column and check constraint the models
   have but the database lacks. The DDL is generated from the ORM models, so it can't drift from them. New columns
   all have defaults, so existing rows stay valid.
2. Catalog data: add new diseases, items, injuries and mutations. Existing catalog rows are referenced by player data
   (and protected by RESTRICT foreign keys), so they are never deleted. Existing items are refreshed in place.
3. Backfill what the new hourly tick expects:
   - pooches that are already pregnant get a pregnancy timer (otherwise they'd never give birth);
   - every pooch's hourly food consumption and mess output are recomputed from its size and breeds, as
     ``create_pooch`` does for new pooches;
   - every born pooch without a ``birth_hour`` gets one from the last 24 hours, so birthdays are spread across the
     game day and the first pooches age on the next tick (instead of all of them aging together a day later);
   - optionally (``--starting-food N``) every kennel is topped up to at least N food units, so existing pooches
     don't start starving the moment the hourly tick runs. Re-running never adds more.
4. Owner event response windows are synced from ``resources/owner_events`` (a reset is the only other way to change
   them, and it wipes players). Only ``response_timeout`` is touched.
5. Validate the cross references between catalogs.

Run with ``uv run python main.py --migrate [--starting-food N]``.
"""

from __future__ import annotations

import random
from typing import Optional

from sqlalchemy import CheckConstraint, inspect, select, text
from sqlalchemy.schema import AddConstraint, CreateColumn

from src.logger import get_logger

from ..get import get_current_hour
from ..load.load_resources import (
    load_diseases,
    load_injuries,
    load_items,
    load_mutations,
)
from ..load.load_resources.cross_refs import validate_cross_references
from ..load.load_resources.owner_events import OWNER_EVENTS_ROOT
from ..load.load_resources.utils import load_categorized_resource_objects
from ..models import Base, Breed, Event, Kennel, Pooch, PoochBreed, PoochPregnancy
from ..session import _get_engine, session_scope
from ..set import pooch_upkeep

logger = get_logger("database/migrations/lots_of_changes")


def _sync_schema(connection) -> list[str]:
    """Create missing tables, columns and check constraints from the ORM models. Returns what was added."""
    added: list[str] = []
    existing_tables = set(inspect(connection).get_table_names())
    Base.metadata.create_all(connection, checkfirst=True)
    added += [f"table {name}" for name in Base.metadata.tables if name not in existing_tables]

    inspector = inspect(connection)
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # created complete just above
        columns = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in columns:
                ddl = CreateColumn(column).compile(dialect=connection.dialect)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))
                added.append(f"column {table.name}.{column.name}")
        checks = {check["name"] for check in inspector.get_check_constraints(table.name)}
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and constraint.name and constraint.name not in checks:
                connection.execute(AddConstraint(constraint))
                added.append(f"check {table.name}.{constraint.name}")
    return added


async def _backfill_pregnancy_timers(timer_range: tuple[int, int], rng: random.Random) -> int:
    """Give every mother with a pending pregnancy but no timer a timer in ``timer_range`` hours."""
    async with session_scope() as session:
        mother_ids = set((await session.execute(select(PoochPregnancy.mother_id))).scalars().all())
        if not mother_ids:
            return 0
        mothers = (
            (await session.execute(select(Pooch).where(Pooch.id.in_(mother_ids), Pooch.pregnancy_timer.is_(None))))
            .scalars()
            .all()
        )
        for mother in mothers:
            mother.pregnancy_timer = rng.randint(*timer_range)
    return len(mothers)


async def _backfill_upkeep() -> int:
    """Recompute every pooch's consumption and mess output from its size and breeds."""
    async with session_scope() as session:
        breed_parameters: dict[int, list[Optional[dict]]] = {}
        for pooch_id, parameters in (
            await session.execute(
                select(PoochBreed.pooch_id, Breed.parameters).join(Breed, Breed.id == PoochBreed.breed_id)
            )
        ).all():
            breed_parameters.setdefault(pooch_id, []).append(parameters)

        pooches = (await session.execute(select(Pooch))).scalars().all()
        for pooch in pooches:
            pooch.consumption, pooch.mess_output = pooch_upkeep(pooch.size, breed_parameters.get(pooch.id, []))
    return len(pooches)


async def _backfill_birth_hours(rng: random.Random) -> int:
    """Give every born pooch without a ``birth_hour`` a random one from the last 24 game hours."""
    current_hour = await get_current_hour()
    async with session_scope() as session:
        pooches = (
            (await session.execute(select(Pooch).where(Pooch.birth_hour.is_(None), Pooch.age >= 0))).scalars().all()
        )
        for pooch in pooches:
            pooch.birth_hour = current_hour - rng.randrange(24)
    return len(pooches)


async def _stock_kennels(food: int) -> int:
    """Top every kennel with less than ``food`` food units up to ``food``. Returns how many were topped up."""
    async with session_scope() as session:
        kennels = (await session.execute(select(Kennel).where(Kennel.food_stock < food))).scalars().all()
        for kennel in kennels:
            kennel.food_stock = food
    return len(kennels)


async def _sync_owner_event_timeouts() -> list[str]:
    """Set each owner event's response window to its resource file's. Returns the names of the events changed."""
    timeouts = {
        name: attributes.get("response_timeout", 3600)
        for events in load_categorized_resource_objects(OWNER_EVENTS_ROOT, "event").values()
        for name, attributes in events.items()
    }
    changed: list[str] = []
    async with session_scope() as session:
        for event in (await session.execute(select(Event).where(Event.name.in_(timeouts)))).scalars().all():
            if event.response_timeout != timeouts[event.name]:
                event.response_timeout = timeouts[event.name]
                changed.append(event.name)
    return changed


async def upgrade(
    pregnancy_timer_range: tuple[int, int], rng: Optional[random.Random] = None, *, starting_food: int = 0
) -> None:
    """
    Run the whole upgrade. ``pregnancy_timer_range`` is the game's PREGNANCY_TIMER_HOURS_RANGE; ``starting_food``
    (food units, 0 = skip) is the least food every kennel is left with.
    """
    rng = rng or random.Random()

    logger.info("Upgrading schema...")
    async with _get_engine().begin() as connection:
        added = await connection.run_sync(_sync_schema)
    logger.info("Schema: %s", ", ".join(added) if added else "already up to date")

    logger.info("Adding new catalog rows...")
    await load_diseases(only_missing=True)
    await load_injuries(only_missing=True)
    await load_mutations(only_missing=True)
    await load_items(only_missing=True)

    pregnancies = await _backfill_pregnancy_timers(pregnancy_timer_range, rng)
    logger.info("Gave %d pregnant pooch(es) a pregnancy timer.", pregnancies)
    pooches = await _backfill_upkeep()
    logger.info("Recomputed consumption and mess output for %d pooch(es).", pooches)
    birthdays = await _backfill_birth_hours(rng)
    logger.info("Gave %d pooch(es) a birth hour.", birthdays)
    if starting_food > 0:
        kennels = await _stock_kennels(starting_food)
        logger.info("Topped up %d kennel(s) to %d food.", kennels, starting_food)
    retimed = await _sync_owner_event_timeouts()
    logger.info("Owner event response windows: %s", ", ".join(retimed) if retimed else "already up to date")

    await validate_cross_references()
    logger.info("Upgrade complete.")
