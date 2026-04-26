"""Tests for src/database/load/load_resources/stray_events.py."""

import pytest

from src.database.load.load_resources.stray_events import _StrayEventValidator
from src.database.load.load_resources.utils import EventValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_validator(breed_names=None, mutation_names=None, event_names=None):
    return _StrayEventValidator(
        breed_names=breed_names or set(),
        mutation_names=mutation_names or set(),
        event_names=event_names or set(),
    )


# ---------------------------------------------------------------------------
# Valid event structures
# ---------------------------------------------------------------------------


def test_validate_minimal_stray_event():
    """A stray event with one action should pass."""
    v = _make_validator()
    events = {
        "Encounters": {
            "Street Fight": {
                "actions": [{"action_type": "modify_base_health", "parameters": {"selector": "random", "amount": -5}}]
            }
        }
    }
    v.validate_stray_events_json(events)
    v.raise_if_invalid()


def test_validate_stray_event_with_outcomes():
    """A stray event with outcomes should pass."""
    v = _make_validator()
    events = {
        "Encounters": {
            "Street Fight": {
                "outcomes": [
                    {
                        "chance": 1.0,
                        "actions": [
                            {"action_type": "modify_base_health", "parameters": {"selector": "random", "amount": -3}}
                        ],
                    }
                ]
            }
        }
    }
    v.validate_stray_events_json(events)
    v.raise_if_invalid()


def test_validate_stray_event_with_filter():
    """
    Test validate stray event with filter.

    Returns
    -------
    Any
        The result of calling `test_validate_stray_event_with_filter`.
    """

    v = _make_validator()
    events = {
        "Encounters": {
            "Breed Added": {
                "filter": {"pooches": [{"min_count": 1}]},
                "actions": [{"action_type": "add_breed", "parameters": {"selector": "random"}}],
            }
        }
    }
    v.validate_stray_events_json(events)
    v.raise_if_invalid()


# ---------------------------------------------------------------------------
# Invalid event structures
# ---------------------------------------------------------------------------


def test_validate_stray_event_root_not_dict():
    """
    Test validate stray event root not dict.

    Returns
    -------
    Any
        The result of calling `test_validate_stray_event_root_not_dict`.
    """

    v = _make_validator()
    v.validate_stray_events_json([])
    with pytest.raises(EventValidationError, match="root value must be an object"):
        v.raise_if_invalid()


def test_validate_stray_event_no_actions_or_outcomes():
    """Stray events must have at least one action or outcome."""
    v = _make_validator()
    v.validate_stray_events_json({"cat": {"event": {}}})
    with pytest.raises(EventValidationError, match="must define at least one action or outcome"):
        v.raise_if_invalid()


def test_validate_stray_event_invalid_action_type():
    """
    Test validate stray event invalid action type.

    Returns
    -------
    Any
        The result of calling `test_validate_stray_event_invalid_action_type`.
    """

    v = _make_validator()
    v.validate_stray_events_json({"cat": {"event": {"actions": [{"action_type": "fly_away", "parameters": {}}]}}})
    with pytest.raises(EventValidationError, match="action_type"):
        v.raise_if_invalid()


def test_validate_stray_event_unknown_keys():
    """
    Test validate stray event unknown keys.

    Returns
    -------
    Any
        The result of calling `test_validate_stray_event_unknown_keys`.
    """

    v = _make_validator()
    v.validate_stray_events_json(
        {
            "cat": {
                "event": {
                    "bogus_field": True,
                    "actions": [{"action_type": "kill_pooch", "parameters": {"selector": "random"}}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="unknown keys"):
        v.raise_if_invalid()


def test_validate_stray_event_invalid_selector():
    """
    Test validate stray event invalid selector.

    Returns
    -------
    Any
        The result of calling `test_validate_stray_event_invalid_selector`.
    """

    v = _make_validator()
    v.validate_stray_events_json(
        {"cat": {"event": {"actions": [{"action_type": "kill_pooch", "parameters": {"selector": "chosen_one"}}]}}}
    )
    with pytest.raises(EventValidationError, match="selector"):
        v.raise_if_invalid()


def test_validate_stray_outcome_chances_exceed_one():
    """
    Test validate stray outcome chances exceed one.

    Returns
    -------
    Any
        The result of calling `test_validate_stray_outcome_chances_exceed_one`.
    """

    v = _make_validator()
    v.validate_stray_events_json(
        {
            "cat": {
                "event": {
                    "outcomes": [
                        {
                            "chance": 0.8,
                            "actions": [{"action_type": "kill_pooch", "parameters": {"selector": "random"}}],
                        },
                        {
                            "chance": 0.8,
                            "actions": [{"action_type": "kill_pooch", "parameters": {"selector": "random"}}],
                        },
                    ]
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="exceeds 1.0"):
        v.raise_if_invalid()
