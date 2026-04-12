"""Tests for src/database/load/load_resources/diseases.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.load.load_resources.diseases import validate_diseases_json
from src.database.load.load_resources.utils import ResourceValidationError

# ---------------------------------------------------------------------------
# validate_diseases_json - valid payloads
# ---------------------------------------------------------------------------


def test_validate_diseases_json_valid_minimal():
    """A disease with only health_impact (required) should pass."""
    diseases = {"Viral": {"Kennel Cough": {"health_impact": "harmful"}}}
    validate_diseases_json(diseases)  # should not raise


def test_validate_diseases_json_valid_full():
    """A disease with every valid attribute should pass."""
    diseases = {
        "Viral": {
            "Kennel Cough": {
                "health_impact": "harmful",
                "description": "Respiratory infection.",
                "contagion_chance": 0.5,
                "sexually_transmitted": False,
                "recovery_chance": 0.3,
                "treatable": True,
                "curable": True,
                "immunity_duration": 30,
                "heritability": 0.1,
                "seasons": ["winter", "autumn"],
                "season_contagion_modifiers": {"winter": 1.5, "summer": 0.5},
                "parameters": {"base_health_add": -2, "constitution_mult": 0.9},
                "visible": True,
                "invisible_messages": ["Your pooch sneezes."],
                "reveal_chance": 0.8,
            }
        }
    }
    validate_diseases_json(diseases)


def test_validate_diseases_json_multiple_categories():
    """Multiple categories with multiple diseases should pass."""
    diseases = {
        "Viral": {
            "Kennel Cough": {"health_impact": "harmful"},
            "Distemper": {"health_impact": "severe"},
        },
        "Parasitic": {
            "Fleas": {"health_impact": "neutral"},
        },
    }
    validate_diseases_json(diseases)


def test_validate_diseases_json_valid_with_parameters_death_message():
    """A disease with parameters including death_message should pass."""
    diseases = {
        "Fatal": {
            "Rabies": {
                "health_impact": "severe",
                "parameters": {
                    "base_health_add": -5,
                    "death_message": "succumbed to rabies",
                },
            }
        }
    }
    validate_diseases_json(diseases)


# ---------------------------------------------------------------------------
# validate_diseases_json - invalid payloads
# ---------------------------------------------------------------------------


def test_validate_diseases_json_not_dict_raises():
    """Root value must be a dict."""
    with pytest.raises(ResourceValidationError, match="root value must be an object"):
        validate_diseases_json("bad")


def test_validate_diseases_json_category_not_dict_raises():
    """Category value must be a dict."""
    with pytest.raises(ResourceValidationError, match="category value must be an object"):
        validate_diseases_json({"cat": "bad"})


def test_validate_diseases_json_disease_not_dict_raises():
    """Disease definition must be a dict."""
    with pytest.raises(ResourceValidationError, match="disease definition must be an object"):
        validate_diseases_json({"cat": {"disease": 123}})


def test_validate_diseases_json_missing_health_impact_raises():
    """Missing required health_impact should raise."""
    with pytest.raises(ResourceValidationError, match="missing required key 'health_impact'"):
        validate_diseases_json({"cat": {"disease": {}}})


def test_validate_diseases_json_invalid_health_impact_raises():
    """Invalid health_impact value should raise."""
    with pytest.raises(ResourceValidationError, match="invalid health_impact"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "superbad"}}})


def test_validate_diseases_json_unknown_keys_raises():
    """Unknown top-level disease keys should raise."""
    with pytest.raises(ResourceValidationError, match="unknown keys"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "bogus": True}}})


def test_validate_diseases_json_contagion_chance_negative_raises():
    """Negative contagion_chance should raise."""
    with pytest.raises(ResourceValidationError, match="contagion_chance"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "contagion_chance": -0.1}}})


def test_validate_diseases_json_contagion_chance_above_one_raises():
    """contagion_chance > 1.0 should raise."""
    with pytest.raises(ResourceValidationError, match="contagion_chance"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "contagion_chance": 1.5}}})


def test_validate_diseases_json_recovery_chance_negative_raises():
    """Negative recovery_chance should raise."""
    with pytest.raises(ResourceValidationError, match="recovery_chance"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "recovery_chance": -0.5}}})


def test_validate_diseases_json_recovery_chance_above_one_raises():
    """recovery_chance > 1.0 should raise."""
    with pytest.raises(ResourceValidationError, match="recovery_chance"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "recovery_chance": 2.0}}})


def test_validate_diseases_json_heritability_negative_raises():
    """Negative heritability should raise."""
    with pytest.raises(ResourceValidationError, match="heritability"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "heritability": -0.1}}})


def test_validate_diseases_json_heritability_above_one_raises():
    """heritability > 1.0 should raise."""
    with pytest.raises(ResourceValidationError, match="heritability"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "heritability": 1.5}}})


def test_validate_diseases_json_invalid_season_raises():
    """Invalid season name in seasons list should raise."""
    with pytest.raises(ResourceValidationError, match="not a valid season"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "seasons": ["monsoon"]}}})


def test_validate_diseases_json_invalid_season_contagion_modifier_key_raises():
    """Invalid season key in season_contagion_modifiers should raise."""
    with pytest.raises(ResourceValidationError, match="not a valid season"):
        validate_diseases_json(
            {
                "cat": {
                    "disease": {
                        "health_impact": "harmful",
                        "season_contagion_modifiers": {"monsoon": 1.5},
                    }
                }
            }
        )


def test_validate_diseases_json_season_contagion_modifier_not_number_raises():
    """Non-numeric value in season_contagion_modifiers should raise."""
    with pytest.raises(ResourceValidationError, match="must be a number"):
        validate_diseases_json(
            {
                "cat": {
                    "disease": {
                        "health_impact": "harmful",
                        "season_contagion_modifiers": {"winter": "high"},
                    }
                }
            }
        )


def test_validate_diseases_json_invisible_messages_not_list_raises():
    """invisible_messages must be a list."""
    with pytest.raises(ResourceValidationError, match="invisible_messages"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "invisible_messages": "bad"}}})


def test_validate_diseases_json_invisible_messages_entry_not_string_raises():
    """Each entry in invisible_messages must be a string."""
    with pytest.raises(ResourceValidationError, match="invisible_messages"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "invisible_messages": [123]}}})


def test_validate_diseases_json_reveal_chance_negative_raises():
    """Negative reveal_chance should raise."""
    with pytest.raises(ResourceValidationError, match="reveal_chance"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "reveal_chance": -0.1}}})


def test_validate_diseases_json_reveal_chance_above_one_raises():
    """reveal_chance > 1.0 should raise."""
    with pytest.raises(ResourceValidationError, match="reveal_chance"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "reveal_chance": 1.5}}})


def test_validate_diseases_json_immunity_duration_not_positive_int_raises():
    """immunity_duration must be a positive integer."""
    with pytest.raises(ResourceValidationError, match="immunity_duration"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "immunity_duration": 0}}})


def test_validate_diseases_json_immunity_duration_float_raises():
    """immunity_duration must be an integer, not a float."""
    with pytest.raises(ResourceValidationError, match="immunity_duration"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "immunity_duration": 5.5}}})


def test_validate_diseases_json_sexually_transmitted_not_bool_raises():
    """sexually_transmitted must be a boolean."""
    with pytest.raises(ResourceValidationError, match="sexually_transmitted"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "sexually_transmitted": "yes"}}})


def test_validate_diseases_json_treatable_not_bool_raises():
    """treatable must be a boolean."""
    with pytest.raises(ResourceValidationError, match="treatable"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "treatable": "yes"}}})


def test_validate_diseases_json_curable_not_bool_raises():
    """curable must be a boolean."""
    with pytest.raises(ResourceValidationError, match="curable"):
        validate_diseases_json({"cat": {"disease": {"health_impact": "harmful", "curable": 1}}})


def test_validate_diseases_json_unknown_parameter_key_raises():
    """Unknown key inside parameters should raise."""
    with pytest.raises(ResourceValidationError, match="parameters.*unknown keys"):
        validate_diseases_json(
            {
                "cat": {
                    "disease": {
                        "health_impact": "harmful",
                        "parameters": {"bogus_key": 1},
                    }
                }
            }
        )


def test_validate_diseases_json_non_numeric_stat_parameter_raises():
    """Stat parameter values (not death_message) must be numeric."""
    with pytest.raises(ResourceValidationError, match="must be a number"):
        validate_diseases_json(
            {
                "cat": {
                    "disease": {
                        "health_impact": "harmful",
                        "parameters": {"base_health_add": "lots"},
                    }
                }
            }
        )


# ---------------------------------------------------------------------------
# load_diseases (integration with mock DB)
# ---------------------------------------------------------------------------


async def test_load_diseases_calls_session():
    """load_diseases should open a session, delete existing, and add new records."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    fake_diseases = {
        "Viral": {
            "Kennel Cough": {"health_impact": "harmful", "contagion_chance": 0.5},
        }
    }

    with (
        patch(
            "src.database.load.load_resources.diseases.load_categorized_resource_objects",
            return_value=fake_diseases,
        ),
        patch(
            "src.database.load.load_resources.diseases.session_scope",
            return_value=_FakeScope(),
        ),
    ):
        from src.database.load.load_resources import load_diseases

        await load_diseases()

    mock_session.execute.assert_awaited_once()
    mock_session.add.assert_called_once()
