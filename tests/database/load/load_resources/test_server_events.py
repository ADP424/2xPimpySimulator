"""Tests for src/database/load/load_resources/server_events.py."""

import pytest

from src.database.load.load_resources.server_events import _ServerEventValidator
from src.database.load.load_resources.utils import EventValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_validator(breed_names=None, mutation_names=None, event_names=None):
    return _ServerEventValidator(
        breed_names=breed_names or set(),
        mutation_names=mutation_names or set(),
        event_names=event_names or set(),
    )


# ---------------------------------------------------------------------------
# Valid event structures
# ---------------------------------------------------------------------------


def test_validate_minimal_server_event():
    """A server event with one option should pass."""
    v = _make_validator()
    events = {
        "Contest": {
            "Sunday Pageant": {
                "options": [{"label": "Enter", "description": "Enter the contest."}],
                "outcomes": [
                    {
                        "chance": 1.0,
                        "actions": [
                            {"action_type": "modify_money", "target_type": "owner", "parameters": {"amount": 50}}
                        ],
                    }
                ],
            }
        }
    }
    v.validate_server_events_json(events)
    v.raise_if_invalid()


def test_validate_server_event_with_all_fields():
    v = _make_validator()
    events = {
        "Contest": {
            "Big Event": {
                "description": "A big event",
                "flavor_text": "Wow!",
                "severity": "major",
                "rarity": "rare",
                "min_owners": 2,
                "max_participants": 10,
                "resolution_strategy": "random_winner",
                "options": [{"label": "Join"}],
            }
        }
    }
    v.validate_server_events_json(events)
    v.raise_if_invalid()


# ---------------------------------------------------------------------------
# Invalid event structures
# ---------------------------------------------------------------------------


def test_validate_server_event_root_not_dict():
    v = _make_validator()
    v.validate_server_events_json("bad")
    with pytest.raises(EventValidationError, match="root value must be an object"):
        v.raise_if_invalid()


def test_validate_server_event_no_options():
    """Server events must have at least one option."""
    v = _make_validator()
    v.validate_server_events_json({"cat": {"event": {"options": []}}})
    with pytest.raises(EventValidationError, match="must define at least one option"):
        v.raise_if_invalid()


def test_validate_server_event_invalid_resolution_strategy():
    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "resolution_strategy": "invalid_strategy",
                    "options": [{"label": "Go"}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="resolution_strategy"):
        v.raise_if_invalid()


def test_validate_server_event_unknown_keys():
    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "bogus_field": True,
                    "options": [{"label": "Go"}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="unknown keys"):
        v.raise_if_invalid()


def test_validate_server_outcome_min_rank_exceeds_max():
    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "options": [{"label": "Go"}],
                    "outcomes": [{"min_rank": 5, "max_rank": 2, "actions": []}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="min_rank cannot be greater"):
        v.raise_if_invalid()


def test_validate_server_outcome_chances_exceed_one():
    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "options": [{"label": "Go"}],
                    "outcomes": [
                        {"chance": 0.6, "actions": []},
                        {"chance": 0.6, "actions": []},
                    ],
                }
            }
        }
    )
    with pytest.raises(EventValidationError):
        v.raise_if_invalid()
