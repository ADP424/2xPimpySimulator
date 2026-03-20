"""Tests for src/database/load/load_resources/breeds.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.load.load_resources.breeds import _validate_breeds_json
from src.database.load.load_resources.utils import ResourceValidationError

# ---------------------------------------------------------------------------
# _validate_breeds_json - valid payloads
# ---------------------------------------------------------------------------


def test_validate_breeds_json_valid_minimal():
    """A breed with no extra attributes should pass validation (all defaults)."""
    breeds = {"Retriever": {"Golden Retriever": {}}}
    _validate_breeds_json(breeds)  # should not raise


def test_validate_breeds_json_valid_full():
    """A breed with every valid attribute should pass."""
    breeds = {
        "Retriever": {
            "Golden Retriever": {
                "alt_name": "Goldie",
                "description": "A friendly dog.",
                "rarity": "common",
                "min_size": 5,
                "max_size": 15,
                "parameters": {"sold_by_vendors": True},
            }
        }
    }
    _validate_breeds_json(breeds)  # should not raise


def test_validate_breeds_json_multiple_categories():
    """Multiple categories with multiple breeds should pass."""
    breeds = {
        "Retriever": {"Golden": {}, "Labrador": {}},
        "Sheepdog": {"Border Collie": {"rarity": "uncommon"}},
    }
    _validate_breeds_json(breeds)


# ---------------------------------------------------------------------------
# _validate_breeds_json - invalid payloads
# ---------------------------------------------------------------------------


def test_validate_breeds_json_not_dict_raises():
    """Non-dict root should raise."""
    with pytest.raises(ResourceValidationError, match="root value must be an object"):
        _validate_breeds_json([])


def test_validate_breeds_json_category_not_dict_raises():
    """Category value that's not a dict should be reported."""
    with pytest.raises(ResourceValidationError, match="category value must be an object"):
        _validate_breeds_json({"bad": "not_a_dict"})


def test_validate_breeds_json_breed_not_dict_raises():
    """Breed definition that's not a dict should be reported."""
    with pytest.raises(ResourceValidationError, match="breed definition must be an object"):
        _validate_breeds_json({"cat": {"MyBreed": "nope"}})


def test_validate_breeds_json_unknown_key_raises():
    """Unknown keys in a breed definition should be reported."""
    with pytest.raises(ResourceValidationError, match="unknown keys"):
        _validate_breeds_json({"cat": {"MyBreed": {"bogus_key": 123}}})


def test_validate_breeds_json_invalid_rarity_raises():
    """A rarity not in the RARITY_VALUES set should be reported."""
    with pytest.raises(ResourceValidationError, match="rarity"):
        _validate_breeds_json({"cat": {"MyBreed": {"rarity": "legendary"}}})


def test_validate_breeds_json_min_exceeds_max_raises():
    """min_size > max_size should be reported."""
    with pytest.raises(ResourceValidationError, match="min_size"):
        _validate_breeds_json({"cat": {"MyBreed": {"min_size": 20, "max_size": 5}}})


def test_validate_breeds_json_negative_min_size_raises():
    with pytest.raises(ResourceValidationError, match="min_size"):
        _validate_breeds_json({"cat": {"MyBreed": {"min_size": -1}}})


def test_validate_breeds_json_non_dict_parameters_raises():
    with pytest.raises(ResourceValidationError, match="parameters"):
        _validate_breeds_json({"cat": {"MyBreed": {"parameters": "not_a_dict"}}})


def test_validate_breeds_json_blank_alt_name_raises():
    with pytest.raises(ResourceValidationError, match="alt_name"):
        _validate_breeds_json({"cat": {"MyBreed": {"alt_name": "   "}}})


# ---------------------------------------------------------------------------
# load_breeds (integration with mock DB)
# ---------------------------------------------------------------------------


async def test_load_breeds_calls_session():
    """load_breeds should clear existing breeds and add new ones."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    fake_breeds = {"TestCategory": {"TestBreed": {"rarity": "common", "min_size": 5, "max_size": 10}}}

    with (
        patch("src.database.load.load_resources.breeds.load_categorized_resource_objects", return_value=fake_breeds),
        patch("src.database.load.load_resources.breeds.session_scope", return_value=_FakeScope()),
    ):
        from src.database.load.load_resources.breeds import load_breeds

        await load_breeds()

    # Should have called execute (for delete) and add (for the new breed)
    mock_session.execute.assert_awaited_once()
    mock_session.add.assert_called_once()
