"""Tests for src/database/load/load_resources/mutations.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.load.load_resources import validate_mutations_json
from src.database.load.load_resources.utils import ResourceValidationError

# ---------------------------------------------------------------------------
# validate_mutations_json - valid payloads
# ---------------------------------------------------------------------------


def test_validate_mutations_json_valid_minimal():
    """A mutation with no extra attributes should pass (all defaults)."""
    mutations = {"Blindness": {"Cataracts": {}}}
    validate_mutations_json(mutations)  # should not raise


def test_validate_mutations_json_valid_full():
    """A mutation with every valid attribute should pass."""
    mutations = {
        "Blindness": {
            "Cataracts": {
                "alt_name": "Eye Clouding",
                "description": "Progressive vision loss.",
                "heritability": 50.0,
                "health_impact": "harmful",
                "rarity": "uncommon",
                "affects_males": True,
                "affects_females": True,
                "parameters": {"breeding_cooldown": 1},
            }
        }
    }
    validate_mutations_json(mutations)


def test_validate_mutations_json_multiple_categories():
    """
    Test validate mutations json multiple categories.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_multiple_categories`.
    """

    mutations = {
        "Blindness": {"Cataracts": {}, "Partial Blindness": {}},
        "Blood Disorders": {"Sickle Cell": {"health_impact": "severe"}},
    }
    validate_mutations_json(mutations)


# ---------------------------------------------------------------------------
# validate_mutations_json - invalid payloads
# ---------------------------------------------------------------------------


def test_validate_mutations_json_not_dict_raises():
    """
    Test validate mutations json not dict raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_not_dict_raises`.
    """

    with pytest.raises(ResourceValidationError, match="root value must be an object"):
        validate_mutations_json("bad")


def test_validate_mutations_json_category_not_dict_raises():
    """
    Test validate mutations json category not dict raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_category_not_dict_raises`.
    """

    with pytest.raises(ResourceValidationError, match="category value must be an object"):
        validate_mutations_json({"cat": "bad"})


def test_validate_mutations_json_mutation_not_dict_raises():
    """
    Test validate mutations json mutation not dict raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_mutation_not_dict_raises`.
    """

    with pytest.raises(ResourceValidationError, match="mutation definition must be an object"):
        validate_mutations_json({"cat": {"mut": 123}})


def test_validate_mutations_json_unknown_key_raises():
    """
    Test validate mutations json unknown key raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_unknown_key_raises`.
    """

    with pytest.raises(ResourceValidationError, match="unknown keys"):
        validate_mutations_json({"cat": {"mut": {"bogus": True}}})


def test_validate_mutations_json_invalid_rarity_raises():
    """
    Test validate mutations json invalid rarity raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_invalid_rarity_raises`.
    """

    with pytest.raises(ResourceValidationError, match="rarity"):
        validate_mutations_json({"cat": {"mut": {"rarity": "mythic"}}})


def test_validate_mutations_json_invalid_health_impact_raises():
    """
    Test validate mutations json invalid health impact raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_invalid_health_impact_raises`.
    """

    with pytest.raises(ResourceValidationError, match="health_impact"):
        validate_mutations_json({"cat": {"mut": {"health_impact": "superbad"}}})


def test_validate_mutations_json_heritability_not_number_raises():
    """
    Test validate mutations json heritability not number raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_heritability_not_number_raises`.
    """

    with pytest.raises(ResourceValidationError, match="heritability"):
        validate_mutations_json({"cat": {"mut": {"heritability": "high"}}})


def test_validate_mutations_json_affects_males_not_bool_raises():
    """
    Test validate mutations json affects males not bool raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_affects_males_not_bool_raises`.
    """

    with pytest.raises(ResourceValidationError, match="affects_males"):
        validate_mutations_json({"cat": {"mut": {"affects_males": "yes"}}})


def test_validate_mutations_json_parameters_not_dict_raises():
    """
    Test validate mutations json parameters not dict raises.

    Returns
    -------
    Any
        The result of calling `test_validate_mutations_json_parameters_not_dict_raises`.
    """

    with pytest.raises(ResourceValidationError, match="parameters"):
        validate_mutations_json({"cat": {"mut": {"parameters": [1, 2]}}})


# ---------------------------------------------------------------------------
# load_mutations (integration with mock DB)
# ---------------------------------------------------------------------------


async def test_load_mutations_calls_session():
    """
    Test load mutations calls session.

    Returns
    -------
    Any
        The result of calling `test_load_mutations_calls_session`.
    """

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    fake_mutations = {"TestCategory": {"TestMutation": {"health_impact": "neutral", "rarity": "common"}}}

    with (
        patch(
            "src.database.load.load_resources.mutations.load_categorized_resource_objects", return_value=fake_mutations
        ),
        patch("src.database.load.load_resources.mutations.session_scope", return_value=_FakeScope()),
    ):
        from src.database.load.load_resources import load_mutations

        await load_mutations()

    mock_session.execute.assert_awaited_once()
    mock_session.add.assert_called_once()


def test_validate_mutations_json_misspelled_stat_raises():
    """A modifier for a stat that doesn't exist (a typo) fails the load instead of doing nothing."""

    with pytest.raises(ResourceValidationError, match="strenght_mult"):
        validate_mutations_json({"cat": {"mut": {"parameters": {"strenght_mult": 1.5}}}})


def test_validate_mutations_json_known_modifiers_pass():
    """Stat modifiers and the value modifiers mutations use are allowed."""

    parameters = {"strength_mult": 1.5, "dollar_value_add": 10, "bloodskull_value_mult": 2, "breeding_cooldown": 5}
    validate_mutations_json({"cat": {"mut": {"parameters": parameters}}})  # should not raise
