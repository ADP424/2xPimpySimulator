"""Tests for src/game/events/shared/utils.py."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.shared import (
    apply_baby_overrides,
    apply_random_mutations,
    build_clone_kwargs,
    build_pooch_kwargs,
    copy_pooch_genetics,
    deliver_to_any_kennel,
    deliver_to_vendor,
    resolve_save_as_specs,
)

MOD = "src.game.events.shared.utils"


@pytest.fixture
def rng() -> random.Random:
    """
    Rng.

    Returns
    -------
    Any
        The result of calling `rng`.
    """

    return random.Random(42)


# ===========================================================================
# resolve_save_as_specs
# ===========================================================================


def test_resolve_save_as_string():
    """
    Test resolve save as string.

    Returns
    -------
    Any
        The result of calling `test_resolve_save_as_string`.
    """

    result = resolve_save_as_specs("my_slot")
    assert result == [{"slot": "my_slot", "target": "clone"}]


def test_resolve_save_as_list_of_dicts():
    """
    Test resolve save as list of dicts.

    Returns
    -------
    Any
        The result of calling `test_resolve_save_as_list_of_dicts`.
    """

    specs = [{"slot": "src", "target": "source"}, {"slot": "clone", "target": "clone"}]
    result = resolve_save_as_specs(specs)
    assert result == specs


def test_resolve_save_as_list_filters_non_dicts():
    """
    Test resolve save as list filters non dicts.

    Returns
    -------
    Any
        The result of calling `test_resolve_save_as_list_filters_non_dicts`.
    """

    specs = [{"slot": "s", "target": "clone"}, "bad", 42]
    result = resolve_save_as_specs(specs)
    assert result == [{"slot": "s", "target": "clone"}]


def test_resolve_save_as_none_returns_empty():
    """
    Test resolve save as none returns empty.

    Returns
    -------
    Any
        The result of calling `test_resolve_save_as_none_returns_empty`.
    """

    result = resolve_save_as_specs(None)
    assert result == []


def test_resolve_save_as_unknown_type_returns_empty():
    """
    Test resolve save as unknown type returns empty.

    Returns
    -------
    Any
        The result of calling `test_resolve_save_as_unknown_type_returns_empty`.
    """

    result = resolve_save_as_specs(123)
    assert result == []


# ===========================================================================
# build_clone_kwargs
# ===========================================================================


def test_build_clone_kwargs_uses_source_fields(rng):
    """
    Test build clone kwargs uses source fields.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_build_clone_kwargs_uses_source_fields`.
    """

    source = SimpleNamespace(
        name="Rex",
        sex="M",
        age=3,
        base_health=10,
        strength=8,
        cuteness=6,
        fluffiness=5,
        intelligence=7,
        dexterity=9,
        fertility=4,
        aggressiveness=3,
        constitution=6,
        size=12,
        breeding_cooldown=0,
    )
    kwargs = build_clone_kwargs(source, {}, rng)
    assert kwargs["name"] == "Rex"
    assert kwargs["sex"] == "M"
    assert kwargs["size"] == 12
    assert kwargs["rng"] is rng


def test_build_clone_kwargs_overrides_with_parameters(rng):
    """
    Test build clone kwargs overrides with parameters.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_build_clone_kwargs_overrides_with_parameters`.
    """

    source = SimpleNamespace(
        name="Rex",
        sex="M",
        age=3,
        base_health=10,
        strength=8,
        cuteness=6,
        fluffiness=5,
        intelligence=7,
        dexterity=9,
        fertility=4,
        aggressiveness=3,
        constitution=6,
        size=12,
        breeding_cooldown=0,
    )
    kwargs = build_clone_kwargs(source, {"name": "Clone", "age": 1}, rng)
    assert kwargs["name"] == "Clone"
    assert kwargs["age"] == 1
    assert kwargs["size"] == 12  # not overridable


# ===========================================================================
# build_pooch_kwargs
# ===========================================================================


@pytest.mark.asyncio
async def test_build_pooch_kwargs_basic(rng):
    """
    Test build pooch kwargs basic.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_build_pooch_kwargs_basic`.
    """

    params = {"name": "Fluffy", "sex": "F", "age": 2, "base_health": 8}
    kwargs = await build_pooch_kwargs(params, rng)
    assert kwargs["name"] == "Fluffy"
    assert kwargs["sex"] == "F"
    assert kwargs["age"] == 2
    assert kwargs["rng"] is rng


@pytest.mark.asyncio
async def test_build_pooch_kwargs_breeds_as_list(rng):
    """
    Test build pooch kwargs breeds as list.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_build_pooch_kwargs_breeds_as_list`.
    """

    params = {"breeds": ["Labrador", "Poodle"]}
    kwargs = await build_pooch_kwargs(params, rng)
    assert kwargs["breeds"] == ["Labrador", "Poodle"]


@pytest.mark.asyncio
async def test_build_pooch_kwargs_breeds_as_int(rng):
    """
    Test build pooch kwargs breeds as int.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_build_pooch_kwargs_breeds_as_int`.
    """

    params = {"breeds": 2}
    with patch(f"{MOD}.get_random_breed_ids", new=AsyncMock(return_value=[1, 2])):
        kwargs = await build_pooch_kwargs(params, rng)
    assert kwargs["breeds"] == [1, 2]


# ===========================================================================
# apply_random_mutations
# ===========================================================================


@pytest.mark.asyncio
async def test_apply_random_mutations_int(rng):
    """
    Test apply random mutations int.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_apply_random_mutations_int`.
    """

    with patch(f"{MOD}.add_mutation_to_pooch", new=AsyncMock()) as mock_add:
        await apply_random_mutations(99, 3, rng)
    assert mock_add.await_count == 3


@pytest.mark.asyncio
async def test_apply_random_mutations_zero_noop(rng):
    """
    Test apply random mutations zero noop.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_apply_random_mutations_zero_noop`.
    """

    with patch(f"{MOD}.add_mutation_to_pooch", new=AsyncMock()) as mock_add:
        await apply_random_mutations(99, 0, rng)
    mock_add.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_random_mutations_non_int_noop(rng):
    """
    Test apply random mutations non int noop.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_apply_random_mutations_non_int_noop`.
    """

    with patch(f"{MOD}.add_mutation_to_pooch", new=AsyncMock()) as mock_add:
        await apply_random_mutations(99, "lots", rng)  # type: ignore[arg-type]
    mock_add.assert_not_awaited()


# ===========================================================================
# copy_pooch_genetics
# ===========================================================================


@pytest.mark.asyncio
async def test_copy_pooch_genetics_copies_breeds_and_mutations():
    """
    Test copy pooch genetics copies breeds and mutations.

    Returns
    -------
    Any
        The result of calling `test_copy_pooch_genetics_copies_breeds_and_mutations`.
    """

    breed_weights = [(1, 0.8), (2, 0.2)]
    mut1 = SimpleNamespace(id=5)
    mut2 = SimpleNamespace(id=6)

    with (
        patch(f"{MOD}.list_pooch_breed_weights", new=AsyncMock(return_value=breed_weights)),
        patch(f"{MOD}.add_pooch_breeds", new=AsyncMock()) as mock_breeds,
        patch(f"{MOD}.list_pooch_mutations", new=AsyncMock(return_value=[mut1, mut2])),
        patch(f"{MOD}.add_mutation_to_pooch", new=AsyncMock()) as mock_muts,
        patch(f"{MOD}.copy_pooch_injuries", new=AsyncMock()) as mock_injuries,
    ):
        await copy_pooch_genetics(10, 11)

    mock_breeds.assert_awaited_once_with(11, dict(breed_weights))
    assert mock_muts.await_count == 2
    mock_injuries.assert_awaited_once_with(10, 11)


@pytest.mark.asyncio
async def test_copy_pooch_genetics_no_breeds_skips_add():
    """
    Test copy pooch genetics no breeds skips add.

    Returns
    -------
    Any
        The result of calling `test_copy_pooch_genetics_no_breeds_skips_add`.
    """

    with (
        patch(f"{MOD}.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.add_pooch_breeds", new=AsyncMock()) as mock_breeds,
        patch(f"{MOD}.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.add_mutation_to_pooch", new=AsyncMock()),
        patch(f"{MOD}.copy_pooch_injuries", new=AsyncMock()),
    ):
        await copy_pooch_genetics(10, 11)

    mock_breeds.assert_not_awaited()


# ===========================================================================
# apply_baby_overrides
# ===========================================================================


@pytest.mark.asyncio
async def test_apply_baby_overrides_name_and_age():
    """
    Test apply baby overrides name and age.

    Returns
    -------
    Any
        The result of calling `test_apply_baby_overrides_name_and_age`.
    """

    with (
        patch(f"{MOD}.rename_pooch", new=AsyncMock()) as mock_rename,
        patch(f"{MOD}.modify_pooch_age", new=AsyncMock()) as mock_age,
        patch(f"{MOD}.modify_pooch_base_health", new=AsyncMock()),
        patch(f"{MOD}.set_pooch_breeding_cooldown", new=AsyncMock()),
    ):
        await apply_baby_overrides(42, {"baby_name": "Puppy", "baby_age": 0})

    mock_rename.assert_awaited_once_with(42, "Puppy")
    mock_age.assert_awaited_once_with(42, 0)


@pytest.mark.asyncio
async def test_apply_baby_overrides_empty_noop():
    """
    Test apply baby overrides empty noop.

    Returns
    -------
    Any
        The result of calling `test_apply_baby_overrides_empty_noop`.
    """

    with (
        patch(f"{MOD}.rename_pooch", new=AsyncMock()) as mock_rename,
        patch(f"{MOD}.modify_pooch_age", new=AsyncMock()),
        patch(f"{MOD}.modify_pooch_base_health", new=AsyncMock()),
        patch(f"{MOD}.set_pooch_breeding_cooldown", new=AsyncMock()),
    ):
        await apply_baby_overrides(42, {})

    mock_rename.assert_not_awaited()


# ===========================================================================
# deliver_to_any_kennel
# ===========================================================================


@pytest.mark.asyncio
async def test_deliver_to_any_kennel_success(rng):
    """
    Test deliver to any kennel success.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_deliver_to_any_kennel_success`.
    """

    owner = SimpleNamespace(discord_id=1)
    kennel = SimpleNamespace(id=10, pooch_limit=5)

    with (
        patch(f"{MOD}.list_owners", new=AsyncMock(return_value=[owner])),
        patch(f"{MOD}.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch(f"{MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.remove_pooch_from_strays", new=AsyncMock()),
        patch(f"{MOD}.cancel_listing_for_pooch", new=AsyncMock()),
        patch(f"{MOD}.transfer_pooch_to_owner", new=AsyncMock()),
        patch(f"{MOD}.add_pooch_to_kennel", new=AsyncMock()),
    ):
        result = await deliver_to_any_kennel(99, 100, rng)

    assert result is True


@pytest.mark.asyncio
async def test_deliver_to_any_kennel_no_space_returns_false(rng):
    """
    Test deliver to any kennel no space returns false.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_deliver_to_any_kennel_no_space_returns_false`.
    """

    owner = SimpleNamespace(discord_id=1)
    kennel = SimpleNamespace(id=10, pooch_limit=1)
    pooches = [SimpleNamespace(id=1)]

    with (
        patch(f"{MOD}.list_owners", new=AsyncMock(return_value=[owner])),
        patch(f"{MOD}.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch(f"{MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=pooches)),
    ):
        result = await deliver_to_any_kennel(99, 100, rng)

    assert result is False


# ===========================================================================
# deliver_to_vendor
# ===========================================================================


@pytest.mark.asyncio
async def test_deliver_to_vendor_success(rng):
    """
    Test deliver to vendor success.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_deliver_to_vendor_success`.
    """

    vendor = SimpleNamespace(id=1)

    with (
        patch(f"{MOD}.list_vendors", new=AsyncMock(return_value=[vendor])),
        patch(f"{MOD}.remove_pooch_from_strays", new=AsyncMock()),
        patch(f"{MOD}.cancel_listing_for_pooch", new=AsyncMock()),
        patch(f"{MOD}.transfer_pooch_to_vendor", new=AsyncMock()),
        patch(f"{MOD}.add_pooch_to_vendor_stock", new=AsyncMock()),
    ):
        result = await deliver_to_vendor(99, 100, rng)

    assert result is True


@pytest.mark.asyncio
async def test_deliver_to_vendor_no_vendors_returns_false(rng):
    """
    Test deliver to vendor no vendors returns false.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_deliver_to_vendor_no_vendors_returns_false`.
    """

    with patch(f"{MOD}.list_vendors", new=AsyncMock(return_value=[])):
        result = await deliver_to_vendor(99, 100, rng)

    assert result is False
