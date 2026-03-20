"""Tests for src/database/load/load_resources/mutations.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.load.load_resources.mutations import _validate_mutations_json
from src.database.load.load_resources.utils import ResourceValidationError

# ---------------------------------------------------------------------------
# _validate_mutations_json - valid payloads
# ---------------------------------------------------------------------------


def test_validate_mutations_json_valid_minimal():
    """A mutation with no extra attributes should pass (all defaults)."""
    mutations = {"Blindness": {"Cataracts": {}}}
    _validate_mutations_json(mutations)  # should not raise


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
    _validate_mutations_json(mutations)


def test_validate_mutations_json_multiple_categories():
    mutations = {
        "Blindness": {"Cataracts": {}, "Partial Blindness": {}},
        "Blood Disorders": {"Sickle Cell": {"health_impact": "severe"}},
    }
    _validate_mutations_json(mutations)


# ---------------------------------------------------------------------------
# _validate_mutations_json - invalid payloads
# ---------------------------------------------------------------------------


def test_validate_mutations_json_not_dict_raises():
    with pytest.raises(ResourceValidationError, match="root value must be an object"):
        _validate_mutations_json("bad")


def test_validate_mutations_json_category_not_dict_raises():
    with pytest.raises(ResourceValidationError, match="category value must be an object"):
        _validate_mutations_json({"cat": "bad"})


def test_validate_mutations_json_mutation_not_dict_raises():
    with pytest.raises(ResourceValidationError, match="mutation definition must be an object"):
        _validate_mutations_json({"cat": {"mut": 123}})


def test_validate_mutations_json_unknown_key_raises():
    with pytest.raises(ResourceValidationError, match="unknown keys"):
        _validate_mutations_json({"cat": {"mut": {"bogus": True}}})


def test_validate_mutations_json_invalid_rarity_raises():
    with pytest.raises(ResourceValidationError, match="rarity"):
        _validate_mutations_json({"cat": {"mut": {"rarity": "mythic"}}})


def test_validate_mutations_json_invalid_health_impact_raises():
    with pytest.raises(ResourceValidationError, match="health_impact"):
        _validate_mutations_json({"cat": {"mut": {"health_impact": "superbad"}}})


def test_validate_mutations_json_heritability_not_number_raises():
    with pytest.raises(ResourceValidationError, match="heritability"):
        _validate_mutations_json({"cat": {"mut": {"heritability": "high"}}})


def test_validate_mutations_json_affects_males_not_bool_raises():
    with pytest.raises(ResourceValidationError, match="affects_males"):
        _validate_mutations_json({"cat": {"mut": {"affects_males": "yes"}}})


def test_validate_mutations_json_parameters_not_dict_raises():
    with pytest.raises(ResourceValidationError, match="parameters"):
        _validate_mutations_json({"cat": {"mut": {"parameters": [1, 2]}}})


# ---------------------------------------------------------------------------
# load_mutations (integration with mock DB)
# ---------------------------------------------------------------------------


async def test_load_mutations_calls_session():
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
        from src.database.load.load_resources.mutations import load_mutations

        await load_mutations()

    mock_session.execute.assert_awaited_once()
    mock_session.add.assert_called_once()
