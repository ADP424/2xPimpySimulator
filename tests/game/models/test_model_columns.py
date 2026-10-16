"""The game models must carry every database column the bot and web read from them.

The frontends read game dataclasses, often through ``getattr(obj, name, default)``. A column missing from a dataclass
doesn't fail: it silently shows the default (food stock 0, no body parts, never immortal). This guard catches a new
column that wasn't added to its game model.
"""

import dataclasses

import pytest

from src.database import models as orm
from src.game import models

# Columns deliberately left off the game models (nothing outside the database layer reads them).
NOT_CARRIED = {
    "Owner": {"joined_at"},
    "Kennel": {"created_at", "upgrade_tier"},
    "Pooch": set(),
}


@pytest.mark.parametrize("name", sorted(NOT_CARRIED))
def test_game_model_carries_every_column(name):
    columns = {column.name for column in getattr(orm, name).__table__.columns}
    fields = {field.name for field in dataclasses.fields(getattr(models, name))}
    assert columns - fields - NOT_CARRIED[name] == set()


async def test_converters_copy_food_stock_and_body_parts():
    from types import SimpleNamespace

    kennel = await models.to_kennel(
        SimpleNamespace(id=1, owner_discord_id=None, name="K", pooch_limit=10, messiness=3, food_stock=250)
    )
    assert kennel.food_stock == 250

    owner = await models.to_owner(
        SimpleNamespace(
            discord_id=1,
            discord_name="L",
            dollars=5,
            bloodskulls=1,
            bones=2,
            begged_today=False,
            visited_park_today=False,
            hand_cleaned_today=True,
            hearts=3,
            brains=4,
            eyes=5,
            tails=6,
            teeth=7,
        )
    )
    assert (owner.hand_cleaned_today, owner.hearts, owner.brains, owner.eyes, owner.tails, owner.teeth) == (
        True,
        3,
        4,
        5,
        6,
        7,
    )
