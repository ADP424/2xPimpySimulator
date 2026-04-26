"""Contract tests for src/bot/ui/day_change_status.py."""

from unittest.mock import MagicMock

import discord
import pytest

from src.bot.ui import (
    DayChangeStatusPageSource,
    PublicPaginatorView,
    make_status_view,
)


def _make_server(discord_id=999, event_channel_discord_id=888):
    from src.game.models.server import Server

    return Server(discord_id=discord_id, event_channel_discord_id=event_channel_discord_id)


def _make_pooch(id=1, name="Rex"):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    return pooch


def _make_birth(mother_name="Mama", child_name="Puppy", message="A puppy was born!"):
    mother = _make_pooch(id=1, name=mother_name)
    child = _make_pooch(id=2, name=child_name)
    birth = MagicMock()
    birth.mother = mother
    birth.child = child
    birth.message = message
    return birth


def _make_death(name="Dearly Departed", message="Has passed away."):
    pooch = _make_pooch(id=3, name=name)
    death = MagicMock()
    death.pooch = pooch
    death.message = message
    return death


def _make_other(name="Sparky", message="Something happened."):
    pooch = _make_pooch(id=4, name=name)
    event = MagicMock()
    event.pooch = pooch
    event.message = message
    return event


@pytest.mark.contract
class TestDayChangeStatusPageSource:
    def test_empty_events_page_count_is_1(self):
        server = _make_server()
        source = DayChangeStatusPageSource(
            server=server, births=[], deaths=[], other_events=[], title="Test", description="Desc"
        )
        assert source.page_count() == 1

    def test_page_count_based_on_max_list(self):
        server = _make_server()
        births = [_make_birth() for _ in range(15)]
        source = DayChangeStatusPageSource(
            server=server, births=births, deaths=[], other_events=[], title="Test", description="Desc"
        )
        # 15 births / 10 per page = 2 pages
        assert source.page_count() == 2

    async def test_render_empty(self):
        server = _make_server()
        source = DayChangeStatusPageSource(
            server=server, births=[], deaths=[], other_events=[], title="Day Change", description="Nothing"
        )
        view = MagicMock()
        view.add_item = MagicMock()
        content, embed = await source.render(view, 0)
        assert content is None
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Day Change"

    async def test_render_with_births(self):
        server = _make_server()
        births = [_make_birth(child_name="Pupper", message="Pupper was born!")]
        source = DayChangeStatusPageSource(
            server=server, births=births, deaths=[], other_events=[], title="Day Change", description="1 birth"
        )
        view = MagicMock()
        view.add_item = MagicMock()
        content, embed = await source.render(view, 0)
        assert isinstance(embed, discord.Embed)
        birth_field = next(f for f in embed.fields if "Birth" in f.name)
        assert "Pupper was born!" in birth_field.value

    async def test_render_with_deaths(self):
        server = _make_server()
        deaths = [_make_death(name="OldDog", message="OldDog passed.")]
        source = DayChangeStatusPageSource(
            server=server, births=[], deaths=deaths, other_events=[], title="Day Change", description="1 death"
        )
        view = MagicMock()
        view.add_item = MagicMock()
        content, embed = await source.render(view, 0)
        death_field = next(f for f in embed.fields if "Death" in f.name)
        assert "OldDog passed." in death_field.value

    async def test_load_is_noop(self):
        server = _make_server()
        source = DayChangeStatusPageSource(
            server=server, births=[], deaths=[], other_events=[], title="T", description="D"
        )
        result = await source.load()
        assert result is None


@pytest.mark.contract
class TestPublicPaginatorView:
    async def test_anyone_can_interact(self):
        source = MagicMock()
        source.load = MagicMock()
        source.page_count = MagicMock(return_value=1)
        view = PublicPaginatorView(source)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        assert await view.interaction_check(interaction) is True


@pytest.mark.contract
class TestMakeStatusView:
    async def test_returns_public_paginator_view(self):
        server = _make_server()
        view = make_status_view(
            server=server,
            births=[],
            deaths=[],
            other_events=[],
            title="Status",
            description="Nothing",
        )
        assert isinstance(view, PublicPaginatorView)
