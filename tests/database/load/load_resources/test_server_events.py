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


def _minimal_menu():
    return {
        "enter": {
            "label": "Enter",
            "options": [{"label": "Join", "description": "Join the event."}],
        }
    }


# ---------------------------------------------------------------------------
# Valid event structures
# ---------------------------------------------------------------------------


def test_validate_minimal_server_event():
    """A server event with one menu and outcome should pass."""
    v = _make_validator()
    events = {
        "Contest": {
            "Sunday Pageant": {
                "menus": _minimal_menu(),
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
    """
    Test validate server event with all fields.

    Returns
    -------
    Any
        The result of calling `test_validate_server_event_with_all_fields`.
    """

    v = _make_validator()
    events = {
        "Contest": {
            "Big Event": {
                "description": "A big event",
                "flavor_text": "Wow!",
                "severity": "major",
                "rarity": "rare",
                "filter": {"min_owners": 2},
                "menus": _minimal_menu(),
            }
        }
    }
    v.validate_server_events_json(events)
    v.raise_if_invalid()


def test_validate_server_event_with_filter_block():
    """
    Test validate server event with filter block.

    Returns
    -------
    Any
        The result of calling `test_validate_server_event_with_filter_block`.
    """

    v = _make_validator()
    events = {
        "Community": {
            "Stray Festival": {
                "filter": {
                    "min_strays": 3,
                    "max_strays": 20,
                    "stray_pooches": [{"min_count": 1}],
                },
                "menus": _minimal_menu(),
            }
        }
    }
    v.validate_server_events_json(events)
    v.raise_if_invalid()


def test_validate_server_event_with_scoring():
    """
    Test validate server event with scoring.

    Returns
    -------
    Any
        The result of calling `test_validate_server_event_with_scoring`.
    """

    v = _make_validator()
    events = {
        "Contest": {
            "Health Cup": {
                "menus": {
                    "enter": {
                        "label": "Enter",
                        "options": [
                            {
                                "label": "Submit pooch",
                                "requires": {"pooch": {"filter": {}}},
                                "scoring": {
                                    "aggregate": "max",
                                    "sources": [
                                        {"type": "pooch_stat", "stat": "base_health", "scale": 1.0, "pivot": 0.0}
                                    ],
                                },
                                "actions": [],
                            }
                        ],
                    }
                },
            }
        }
    }
    v.validate_server_events_json(events)
    v.raise_if_invalid()


# ---------------------------------------------------------------------------
# Invalid event structures
# ---------------------------------------------------------------------------


def test_validate_server_event_root_not_dict():
    """
    Test validate server event root not dict.

    Returns
    -------
    Any
        The result of calling `test_validate_server_event_root_not_dict`.
    """

    v = _make_validator()
    v.validate_server_events_json("bad")
    with pytest.raises(EventValidationError, match="root value must be an object"):
        v.raise_if_invalid()


def test_validate_server_event_no_menus_no_actions():
    """Server events with no menus and no actions/outcomes should fail."""
    v = _make_validator()
    v.validate_server_events_json({"cat": {"event": {"description": "nothing here"}}})
    with pytest.raises(EventValidationError, match="must define actions, menus, or outcomes"):
        v.raise_if_invalid()


def test_validate_server_event_unknown_keys():
    """
    Test validate server event unknown keys.

    Returns
    -------
    Any
        The result of calling `test_validate_server_event_unknown_keys`.
    """

    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "bogus_field": True,
                    "menus": _minimal_menu(),
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="unknown keys"):
        v.raise_if_invalid()


def test_validate_server_event_old_keys_rejected():
    """Old keys like options, min_owners, resolution_strategy should be rejected."""
    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "min_owners": 1,
                    "resolution_strategy": "random_winner",
                    "options": [{"label": "Go"}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="unknown keys"):
        v.raise_if_invalid()


def test_validate_server_outcome_min_rank_exceeds_max():
    """
    Test validate server outcome min rank exceeds max.

    Returns
    -------
    Any
        The result of calling `test_validate_server_outcome_min_rank_exceeds_max`.
    """

    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "menus": _minimal_menu(),
                    "outcomes": [{"min_rank": 5, "max_rank": 2, "actions": []}],
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="min_rank cannot be greater"):
        v.raise_if_invalid()


def test_validate_server_outcome_chances_exceed_one():
    """
    Test validate server outcome chances exceed one.

    Returns
    -------
    Any
        The result of calling `test_validate_server_outcome_chances_exceed_one`.
    """

    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "menus": _minimal_menu(),
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


def test_validate_menu_depends_on_unknown_menu():
    """
    Test validate menu depends on unknown menu.

    Returns
    -------
    Any
        The result of calling `test_validate_menu_depends_on_unknown_menu`.
    """

    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "menus": {
                        "boost": {
                            "label": "Boost",
                            "depends_on": ["nonexistent"],
                            "options": [{"label": "Power up"}],
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="references unknown menu"):
        v.raise_if_invalid()


def test_validate_invalid_scoring_aggregate():
    """
    Test validate invalid scoring aggregate.

    Returns
    -------
    Any
        The result of calling `test_validate_invalid_scoring_aggregate`.
    """

    v = _make_validator()
    v.validate_server_events_json(
        {
            "cat": {
                "event": {
                    "menus": {
                        "enter": {
                            "label": "Enter",
                            "options": [
                                {
                                    "label": "Go",
                                    "scoring": {"aggregate": "invalid_agg", "sources": []},
                                    "actions": [],
                                }
                            ],
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(EventValidationError, match="aggregate"):
        v.raise_if_invalid()
