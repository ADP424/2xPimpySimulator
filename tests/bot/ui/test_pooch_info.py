"""Contract tests for src/bot/ui/pooch_info.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.pooch_info import (
    PoochInfoView,
    _BreedSelect,
    _FamilySelect,
    _MutationSelect,
)


def _make_pooch(
    id=1,
    name="Rex",
    age=3,
    sex="male",
    base_health=100,
    health_loss_age=5,
    strength=10,
    cuteness=10,
    fluffiness=10,
    intelligence=10,
    dexterity=10,
    fertility=10,
    aggressiveness=5,
    constitution=10,
    breeding_cooldown=0,
    alive=True,
    virgin=True,
    owner_discord_id=100,
    vendor_id=None,
    size=50,
    health=95,
    breeds=None,
    mutations=None,
):
    from src.game.models.pooch import Pooch

    return Pooch(
        id=id,
        name=name,
        age=age,
        sex=sex,
        base_health=base_health,
        health_loss_age=health_loss_age,
        strength=strength,
        cuteness=cuteness,
        fluffiness=fluffiness,
        intelligence=intelligence,
        dexterity=dexterity,
        fertility=fertility,
        aggressiveness=aggressiveness,
        constitution=constitution,
        breeding_cooldown=breeding_cooldown,
        alive=alive,
        virgin=virgin,
        vet_checked=False,
        owner_discord_id=owner_discord_id,
        vendor_id=vendor_id,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        size=size,
        health=health,
        mood=None,
        owner=None,
        vendor=None,
        breeds=breeds or [],
        mutations=mutations or [],
        injuries=[],
        diseases=[],
    )


def _make_server(discord_id=999, event_channel_discord_id=888):
    from src.game.models.server import Server

    return Server(discord_id=discord_id, event_channel_discord_id=event_channel_discord_id)


def _make_owner(discord_id=100, dollars=500, bloodskulls=3, bones=1):
    from src.game.models.owner import Owner

    return Owner(discord_id=discord_id, discord_name="TestUser", dollars=dollars, bloodskulls=bloodskulls, bones=bones)


@pytest.mark.contract
class TestPoochInfoView:
    async def test_creates_view(self):
        server = _make_server()
        pooch = _make_pooch()
        view = PoochInfoView(server=server, pooch=pooch, owner=None)
        assert isinstance(view, discord.ui.View)

    async def test_interaction_check_allows_anyone_when_no_owner(self):
        server = _make_server()
        pooch = _make_pooch()
        view = PoochInfoView(server=server, pooch=pooch, owner=None)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999
        assert await view.interaction_check(interaction) is True

    async def test_interaction_check_restricts_to_owner(self):
        server = _make_server()
        pooch = _make_pooch()
        owner = _make_owner(discord_id=100)
        view = PoochInfoView(server=server, pooch=pooch, owner=owner)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False

    async def test_build_embed_basic(self):
        server = _make_server()
        pooch = _make_pooch(name="Buddy", age=5, sex="female")

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [], "children": [], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            embed = await view.build_embed()

        assert isinstance(embed, discord.Embed)
        assert embed.title == "Buddy"
        field_names = [f.name for f in embed.fields]
        assert "Age" in field_names
        assert "Sex" in field_names
        assert "Health Status" in field_names

    async def test_build_embed_with_family(self):
        server = _make_server()
        pooch = _make_pooch()
        parent = _make_pooch(id=2, name="Mom")
        child = _make_pooch(id=3, name="Junior")

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [parent], "children": [child], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            embed = await view.build_embed()

        parents_field = next(f for f in embed.fields if f.name == "Parents")
        assert "Mom" in parents_field.value
        children_field = next(f for f in embed.fields if f.name == "Children")
        assert "Junior" in children_field.value

    async def test_build_embed_adds_family_selects(self):
        server = _make_server()
        pooch = _make_pooch()
        parent = _make_pooch(id=2, name="Mom")

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [parent], "children": [], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            await view.build_embed()

        # Should have added a select for parents
        selects = [child for child in view.children if isinstance(child, discord.ui.Select)]
        assert len(selects) >= 1

    def test_format_breeding_status_in_heat(self):
        assert PoochInfoView._format_breeding_status(0) == "In Heat"

    def test_format_breeding_status_heating_up(self):
        assert PoochInfoView._format_breeding_status(3) == "Heating Up"

    def test_format_breeding_status_cooled(self):
        assert PoochInfoView._format_breeding_status(10) == "Cooled"

    def test_format_size(self):
        assert PoochInfoView._format_size(42) == "42"

    async def test_build_embed_with_breeds(self):
        server = _make_server()
        from src.game.models import PoochBreedInfo

        breed = MagicMock()
        breed.id = 1
        breed.name = "Labrador"
        pooch_breed = MagicMock(spec=PoochBreedInfo)
        pooch_breed.breed = breed
        pooch_breed.relative_weight = 0.75

        pooch = _make_pooch(breeds=[pooch_breed])

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [], "children": [], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            embed = await view.build_embed()

        breeds_field = next(f for f in embed.fields if f.name == "Breeds")
        assert "Labrador" in breeds_field.value
        assert "75%" in breeds_field.value

    async def test_build_embed_with_mutations(self):
        server = _make_server()
        mutation = MagicMock()
        mutation.id = 1
        mutation.name = "Cataracts"

        from types import SimpleNamespace

        mutation_info = SimpleNamespace(mutation=mutation, visible=True, displayed_symptom=None)
        pooch = _make_pooch(mutations=[mutation_info])

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [], "children": [], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            embed = await view.build_embed()

        mutations_field = next(f for f in embed.fields if f.name == "Mutations")
        assert "Cataracts" in mutations_field.value

    async def test_build_embed_no_breeds_or_mutations(self):
        server = _make_server()
        pooch = _make_pooch(breeds=[], mutations=[])

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [], "children": [], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            embed = await view.build_embed()

        breeds_field = next(f for f in embed.fields if f.name == "Breeds")
        assert breeds_field.value == "None"
        mutations_field = next(f for f in embed.fields if f.name == "Mutations")
        assert mutations_field.value == "None"

    async def test_build_embed_with_siblings(self):
        server = _make_server()
        pooch = _make_pooch()
        sibling = _make_pooch(id=99, name="Sibling Dog")

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [], "children": [], "siblings": [sibling]},
        ):
            view = PoochInfoView(server=server, pooch=pooch, owner=None)
            embed = await view.build_embed()

        siblings_field = next(f for f in embed.fields if f.name == "Siblings")
        assert "Sibling Dog" in siblings_field.value

    async def test_build_embed_no_owner_shows_nobody(self):
        server = _make_server()
        _make_pooch(owner_discord_id=None)
        pooch_obj = MagicMock()
        pooch_obj.id = 1
        pooch_obj.name = "No Owner"
        pooch_obj.age = 3
        pooch_obj.sex = "male"
        pooch_obj.base_health = 100
        pooch_obj.health = 95
        pooch_obj.health_loss_age = 5
        pooch_obj.strength = 10
        pooch_obj.cuteness = 10
        pooch_obj.fluffiness = 10
        pooch_obj.intelligence = 10
        pooch_obj.dexterity = 10
        pooch_obj.fertility = 10
        pooch_obj.aggressiveness = 5
        pooch_obj.breeding_cooldown = 0
        pooch_obj.alive = True
        pooch_obj.virgin = True
        pooch_obj.owner_discord_id = None
        pooch_obj.vendor = None
        pooch_obj.vendor_id = None
        pooch_obj.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pooch_obj.size = 50
        pooch_obj.owner = None
        pooch_obj.breeds = []
        pooch_obj.mutations = []
        pooch_obj.status = "healthy"
        pooch_obj.birthday = datetime(2024, 1, 1, tzinfo=timezone.utc)

        with patch(
            "src.bot.ui.pooch_info.get_pooch_family",
            new_callable=AsyncMock,
            return_value={"parents": [], "children": [], "siblings": []},
        ):
            view = PoochInfoView(server=server, pooch=pooch_obj, owner=None)
            embed = await view.build_embed()

        owner_field = next(f for f in embed.fields if f.name == "Owner")
        assert "Nobody" in owner_field.value


@pytest.mark.contract
class TestFamilySelect:
    def test_empty_members_shows_disabled_select(self):
        select = _FamilySelect(members=[], placeholder="Parents", kind="parents", empty_label="Unknown parents")
        assert select.disabled is True
        assert len(select.options) == 1
        assert select.options[0].label == "Unknown parents"

    def test_with_members_enables_select(self):
        member = MagicMock()
        member.id = 1
        member.name = "Mom"
        select = _FamilySelect(members=[member], placeholder="Parents", kind="parents", empty_label="Unknown parents")
        assert select.disabled is False
        assert len(select.options) == 1
        assert select.options[0].label == "Mom"

    async def test_callback_none_value_ignored(self):
        select = _FamilySelect(members=[], placeholder="Parents", kind="parents", empty_label="Unknown parents")
        interaction = MagicMock()
        view = MagicMock()
        select._view = view

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["__none__"])),
            patch("src.bot.ui.pooch_info.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)
            mock_r.reply.assert_not_called()

    async def test_callback_valid_member_opens_pooch_info(self):
        server = _make_server()
        member_pooch = _make_pooch(id=5, name="Mom Dog")

        select = _FamilySelect(
            members=[member_pooch],
            placeholder="Parents",
            kind="parents",
            empty_label="Unknown",
        )

        # Mock the view to be a PoochInfoView
        parent_view = PoochInfoView(server=server, pooch=member_pooch, owner=None)
        select._view = parent_view

        interaction = MagicMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["5"])),
            patch("src.bot.ui.pooch_info.InteractionResponder") as MockResponder,
            patch(
                "src.bot.ui.pooch_info.get_pooch_family",
                new_callable=AsyncMock,
                return_value={"parents": [], "children": [], "siblings": []},
            ),
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)
            mock_r.reply.assert_called_once()


@pytest.mark.contract
class TestBreedSelect:
    def test_empty_breeds_shows_disabled_select(self):
        select = _BreedSelect(pooch_breeds=[], placeholder="Breeds", empty_label="No breeds")
        assert select.disabled is True

    def test_with_breeds_shows_enabled_select(self):
        from src.game.models import PoochBreedInfo

        breed = MagicMock()
        breed.id = 1
        breed.name = "Labrador"
        pooch_breed = MagicMock(spec=PoochBreedInfo)
        pooch_breed.breed = breed
        pooch_breed.relative_weight = 0.5
        select = _BreedSelect(pooch_breeds=[pooch_breed], placeholder="Breeds", empty_label="No breeds")
        assert select.disabled is False

    async def test_callback_none_skips_reply(self):
        select = _BreedSelect(pooch_breeds=[], placeholder="Breeds", empty_label="No breeds")
        interaction = MagicMock()
        select._view = MagicMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["__none__"])),
            patch("src.bot.ui.pooch_info.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)
            mock_r.reply.assert_not_called()


@pytest.mark.contract
class TestMutationSelect:
    def test_empty_mutations_shows_disabled_select(self):
        select = _MutationSelect(mutations=[], placeholder="Mutations", empty_label="No mutations")
        assert select.disabled is True

    def test_with_mutations_shows_enabled_select(self):
        mutation = MagicMock()
        mutation.id = 1
        mutation.name = "Cataracts"
        select = _MutationSelect(mutations=[mutation], placeholder="Mutations", empty_label="No mutations")
        assert select.disabled is False

    async def test_callback_none_skips_reply(self):
        select = _MutationSelect(mutations=[], placeholder="Mutations", empty_label="No mutations")
        interaction = MagicMock()
        select._view = MagicMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["__none__"])),
            patch("src.bot.ui.pooch_info.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)
            mock_r.reply.assert_not_called()

    async def test_callback_valid_mutation_shows_embed(self):
        mutation = MagicMock()
        mutation.id = 10
        mutation.name = "Cataracts"
        select = _MutationSelect(mutations=[mutation], placeholder="Mutations", empty_label="No mutations")
        interaction = MagicMock()
        select._view = MagicMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["10"])),
            patch("src.bot.ui.pooch_info.InteractionResponder") as MockResponder,
            patch("src.bot.ui.pooch_info.build_mutation_info_embed", return_value=MagicMock()),
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)
            mock_r.reply.assert_called_once()
