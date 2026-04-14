"""Tests for src/game/rituals.py — clone, rejuvenation, gender change, immortality."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game.constants import (
    CLONE_RITUAL_BLOODSKULLS_MIN,
    CLONE_RITUAL_BLOODSKULLS_VALUE_MULT,
    GENDER_CHANGE_RITUAL_EYE_COST,
    IMMORTALITY_RITUAL_BLOODSKULLS,
    REJUVENATION_RITUAL_BLOODSKULLS,
)
from src.game.manage_rituals import (
    clone_pooch_ritual,
    clone_ritual_cost,
    gender_change_pooch,
    immortalize_pooch,
    rejuvenate_pooch,
)


def make_pooch_full(
    pooch_id=1,
    name="Fido",
    sex="male",
    alive=True,
    pregnancy_timer=None,
    immortal=False,
    owner_discord_id=100,
    **kw,
):
    base = dict(
        id=pooch_id,
        name=name,
        sex=sex,
        alive=alive,
        pregnancy_timer=pregnancy_timer,
        immortal=immortal,
        owner_discord_id=owner_discord_id,
        size=10,
        base_health=10,
        strength=10,
        cuteness=10,
        fluffiness=10,
        intelligence=10,
        dexterity=10,
        fertility=10,
        aggressiveness=10,
        constitution=10,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def make_owner(discord_id=100, dollars=500, bloodskulls=2000, hearts=5, brains=5, eyes=5, tails=5, teeth=5):
    return SimpleNamespace(
        discord_id=discord_id,
        dollars=dollars,
        bloodskulls=bloodskulls,
        bones=10,
        hearts=hearts,
        brains=brains,
        eyes=eyes,
        tails=tails,
        teeth=teeth,
    )


# ---------------------------------------------------------------------------
# Cost calc
# ---------------------------------------------------------------------------


class TestCloneRitualCost:
    def test_minimum_floor(self):
        # Tiny pooch value -> bloodskull cost is the minimum.
        assert clone_ritual_cost(1) == CLONE_RITUAL_BLOODSKULLS_MIN

    def test_scales_with_value(self):
        assert clone_ritual_cost(50) == 50 * CLONE_RITUAL_BLOODSKULLS_VALUE_MULT


# ---------------------------------------------------------------------------
# Clone ritual
# ---------------------------------------------------------------------------


class TestCloneRitual:
    async def test_rejects_unknown_pooch(self):
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=None)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=make_owner())),
        ):
            res = await clone_pooch_ritual(100, 999)
        assert res.success is False
        assert "doesn't exist" in res.message

    async def test_rejects_non_owner(self):
        pooch = make_pooch_full(owner_discord_id=999)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=make_owner())),
        ):
            res = await clone_pooch_ritual(100, 1)
        assert res.success is False
        assert "don't own" in res.message

    async def test_rejects_dead_pooch(self):
        pooch = make_pooch_full(alive=False)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=make_owner())),
        ):
            res = await clone_pooch_ritual(100, 1)
        assert res.success is False
        assert "dead" in res.message

    async def test_rejects_insufficient_bloodskulls(self):
        pooch = make_pooch_full()
        owner = make_owner(bloodskulls=10)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
            patch("src.game.manage_rituals.get_pooch_bloodskull_value", new=AsyncMock(return_value=20)),
        ):
            res = await clone_pooch_ritual(100, 1)
        assert res.success is False
        assert "bloodskulls" in res.message

    async def test_rejects_no_kennel_space(self):
        pooch = make_pooch_full()
        owner = make_owner()
        full_kennel = SimpleNamespace(id=10, pooch_limit=1)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
            patch("src.game.manage_rituals.get_pooch_bloodskull_value", new=AsyncMock(return_value=10)),
            patch("src.game.manage_rituals.list_kennels_for_owner", new=AsyncMock(return_value=[full_kennel])),
            patch("src.game.manage_rituals.list_pooches_for_kennel", new=AsyncMock(return_value=[pooch])),
        ):
            res = await clone_pooch_ritual(100, 1)
        assert res.success is False
        assert "kennel" in res.message.lower()


# ---------------------------------------------------------------------------
# Rejuvenation
# ---------------------------------------------------------------------------


class TestRejuvenation:
    async def test_rejects_insufficient_bloodskulls(self):
        pooch = make_pooch_full()
        owner = make_owner(bloodskulls=10, hearts=5)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        ):
            res = await rejuvenate_pooch(100, 1)
        assert res.success is False
        assert "bloodskull" in res.message

    async def test_rejects_no_hearts(self):
        pooch = make_pooch_full()
        owner = make_owner(bloodskulls=REJUVENATION_RITUAL_BLOODSKULLS, hearts=0)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        ):
            res = await rejuvenate_pooch(100, 1)
        assert res.success is False
        assert "heart" in res.message

    async def test_success_charges_and_resets(self):
        pooch = make_pooch_full(age=8)
        owner = make_owner()
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
            patch("src.game.manage_rituals.give_bloodskulls_to_owner", new=AsyncMock()) as charge_bs,
            patch("src.game.manage_rituals.give_owner_body_part", new=AsyncMock()) as charge_part,
            patch("src.game.manage_rituals.set_pooch_age", new=AsyncMock()) as set_age,
            patch("src.game.manage_rituals.increment_pooch_rejuvenation_count", new=AsyncMock(return_value=1)),
        ):
            res = await rejuvenate_pooch(100, 1)
        assert res.success is True
        charge_bs.assert_awaited_once_with(100, -REJUVENATION_RITUAL_BLOODSKULLS)
        charge_part.assert_awaited_once_with(100, "heart", -1)
        set_age.assert_awaited_once_with(1, 0)


# ---------------------------------------------------------------------------
# Gender change
# ---------------------------------------------------------------------------


class TestGenderChange:
    async def test_rejects_pregnant_pooch(self):
        pooch = make_pooch_full(pregnancy_timer=5)
        owner = make_owner()
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        ):
            res = await gender_change_pooch(100, 1)
        assert res.success is False
        assert "pregnant" in res.message

    async def test_success_flips_sex(self):
        pooch = make_pooch_full(sex="male")
        owner = make_owner()
        flipped = make_pooch_full(sex="female")
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
            patch("src.game.manage_rituals.give_bloodskulls_to_owner", new=AsyncMock()),
            patch("src.game.manage_rituals.give_owner_body_part", new=AsyncMock()) as charge_part,
            patch("src.game.manage_rituals.flip_pooch_sex", new=AsyncMock(return_value=flipped)),
        ):
            res = await gender_change_pooch(100, 1)
        assert res.success is True
        assert "female" in res.message
        charge_part.assert_awaited_once_with(100, "eye", -GENDER_CHANGE_RITUAL_EYE_COST)


# ---------------------------------------------------------------------------
# Immortality
# ---------------------------------------------------------------------------


class TestImmortality:
    async def test_rejects_already_immortal(self):
        pooch = make_pooch_full(immortal=True)
        owner = make_owner()
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        ):
            res = await immortalize_pooch(100, 1)
        assert res.success is False
        assert "already immortal" in res.message

    async def test_rejects_insufficient_resources(self):
        pooch = make_pooch_full()
        # Has bloodskulls but no hearts.
        owner = make_owner(bloodskulls=IMMORTALITY_RITUAL_BLOODSKULLS, hearts=0)
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        ):
            res = await immortalize_pooch(100, 1)
        assert res.success is False
        assert "heart" in res.message

    async def test_success_sets_immortal_flag(self):
        pooch = make_pooch_full()
        owner = make_owner()
        with (
            patch("src.game.manage_rituals.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_rituals.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
            patch("src.game.manage_rituals.give_bloodskulls_to_owner", new=AsyncMock()),
            patch("src.game.manage_rituals.give_owner_body_part", new=AsyncMock()),
            patch("src.game.manage_rituals.set_pooch_immortal", new=AsyncMock()) as set_immortal,
        ):
            res = await immortalize_pooch(100, 1)
        assert res.success is True
        set_immortal.assert_awaited_once_with(1, True)
