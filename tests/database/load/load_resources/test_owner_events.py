"""Tests for src/database/load/load_resources/owner_events.py."""

import pytest

from src.database.load.load_resources.owner_events import _OwnerEventValidator
from src.database.load.load_resources.utils import EventValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_validator(breed_names=None, mutation_names=None, event_names=None):
    return _OwnerEventValidator(
        breed_names=breed_names or set(),
        mutation_names=mutation_names or set(),
        event_names=event_names or set(),
    )


# ---------------------------------------------------------------------------
# Valid event structures
# ---------------------------------------------------------------------------


def test_validate_minimal_event():
    """An event with just one action should pass."""
    v = _make_validator()
    events = {
        "Fortune": {
            "Lucky Find": {
                "actions": [{"action_type": "modify_money", "target_type": "owner", "parameters": {"amount": 100}}]
            }
        }
    }
    v.validate_owner_events_json(events)
    v.raise_if_invalid()


def test_validate_event_with_options_and_outcomes():
    """An event with requires_response, options, and outcomes should pass."""
    v = _make_validator()
    events = {
        "Fortune": {
            "Lucky Find": {
                "requires_response": True,
                "options": [
                    {
                        "label": "Take it",
                        "default": True,
                        "outcomes": [
                            {
                                "chance": 1.0,
                                "actions": [
                                    {
                                        "action_type": "modify_money",
                                        "target_type": "owner",
                                        "parameters": {"amount": 50},
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        }
    }
    v.validate_owner_events_json(events)
    v.raise_if_invalid()


# ---------------------------------------------------------------------------
# Invalid event structures
# ---------------------------------------------------------------------------


def test_validate_root_not_dict():
    """
    Test validate root not dict.

    Returns
    -------
    Any
        The result of calling `test_validate_root_not_dict`.
    """

    v = _make_validator()
    v.validate_owner_events_json("not a dict")
    with pytest.raises(EventValidationError, match="root value must be an object"):
        v.raise_if_invalid()


def test_validate_category_not_dict():
    """
    Test validate category not dict.

    Returns
    -------
    Any
        The result of calling `test_validate_category_not_dict`.
    """

    v = _make_validator()
    v.validate_owner_events_json({"cat": "bad"})
    with pytest.raises(EventValidationError, match="category value must be an object"):
        v.raise_if_invalid()


def test_validate_event_not_dict():
    """
    Test validate event not dict.

    Returns
    -------
    Any
        The result of calling `test_validate_event_not_dict`.
    """

    v = _make_validator()
    v.validate_owner_events_json({"cat": {"event": "bad"}})
    with pytest.raises(EventValidationError, match="event definition must be an object"):
        v.raise_if_invalid()


def test_validate_event_unknown_keys():
    """
    Test validate event unknown keys.

    Returns
    -------
    Any
        The result of calling `test_validate_event_unknown_keys`.
    """

    v = _make_validator()
    v.validate_owner_events_json(
        {
            "cat": {
                "event": {
                    "bogus": True,
                    "actions": [{"action_type": "modify_money", "target_type": "owner", "parameters": {"amount": 1}}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="unknown keys"):
        v.raise_if_invalid()


def test_validate_requires_response_without_options():
    """requires_response=true without options should produce an error."""
    v = _make_validator()
    v.validate_owner_events_json(
        {
            "cat": {
                "event": {
                    "requires_response": True,
                    "options": [],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="requires_response=true events must define"):
        v.raise_if_invalid()


def test_validate_no_actions_or_options():
    """An event with neither actions nor options should produce an error."""
    v = _make_validator()
    v.validate_owner_events_json({"cat": {"event": {}}})
    with pytest.raises(EventValidationError, match="must define at least one action or option"):
        v.raise_if_invalid()


def test_validate_action_invalid_action_type():
    """An unrecognized action_type should produce an error."""
    v = _make_validator()
    v.validate_owner_events_json(
        {"cat": {"event": {"actions": [{"action_type": "invalid_action", "target_type": "owner", "parameters": {}}]}}}
    )
    with pytest.raises(EventValidationError):
        v.raise_if_invalid()


def test_validate_action_invalid_target_type():
    """An unrecognized target_type should produce an error."""
    v = _make_validator()
    v.validate_owner_events_json(
        {
            "cat": {
                "event": {
                    "actions": [
                        {"action_type": "modify_money", "target_type": "spaceship", "parameters": {"amount": 1}}
                    ]
                }
            }
        }
    )
    with pytest.raises(EventValidationError):
        v.raise_if_invalid()


def test_validate_outcome_chances_exceed_one():
    """Outcome chances that sum > 1.0 should produce an error."""
    v = _make_validator()
    v.validate_owner_events_json(
        {
            "cat": {
                "event": {
                    "requires_response": True,
                    "options": [
                        {
                            "label": "Go",
                            "default": True,
                            "outcomes": [
                                {
                                    "chance": 0.7,
                                    "actions": [
                                        {
                                            "action_type": "modify_money",
                                            "target_type": "owner",
                                            "parameters": {"amount": 1},
                                        }
                                    ],
                                },
                                {
                                    "chance": 0.7,
                                    "actions": [
                                        {
                                            "action_type": "modify_money",
                                            "target_type": "owner",
                                            "parameters": {"amount": 2},
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="exceeds 1.0"):
        v.raise_if_invalid()


# ---------------------------------------------------------------------------
# Filter validation
# ---------------------------------------------------------------------------


def test_validate_owner_filter_valid():
    """
    Test validate owner filter valid.

    Returns
    -------
    Any
        The result of calling `test_validate_owner_filter_valid`.
    """

    v = _make_validator()
    v._validate_owner_filter("test", {"min_money": 100, "max_money": 500})
    assert not v.errors


def test_validate_owner_filter_unknown_key():
    """
    Test validate owner filter unknown key.

    Returns
    -------
    Any
        The result of calling `test_validate_owner_filter_unknown_key`.
    """

    v = _make_validator()
    v._validate_owner_filter("test", {"invalid_key": True})
    assert len(v.errors) == 1
    assert "unknown keys" in v.errors[0]


def test_validate_pooch_filter_valid():
    """
    Test validate pooch filter valid.

    Returns
    -------
    Any
        The result of calling `test_validate_pooch_filter_valid`.
    """

    v = _make_validator()
    v._validate_pooch_filter(
        "test", {"min_age": 1, "max_age": 10, "sex": "male"}, allow_counts=False, allow_location=False
    )
    assert not v.errors


def test_validate_pooch_filter_invalid_sex():
    """
    Test validate pooch filter invalid sex.

    Returns
    -------
    Any
        The result of calling `test_validate_pooch_filter_invalid_sex`.
    """

    v = _make_validator()
    v._validate_pooch_filter("test", {"sex": "alien"}, allow_counts=False, allow_location=False)
    assert len(v.errors) == 1
