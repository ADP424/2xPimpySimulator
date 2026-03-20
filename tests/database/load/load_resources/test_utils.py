"""Tests for src/database/load/load_resources/utils.py.

Focuses on the validation helpers and name-list utilities.
"""

from pathlib import Path

import pytest

from src.database.load.load_resources.utils import (
    BaseEventValidator,
    EventValidationError,
    ResourceValidationError,
    load_names_from_root,
    validate_name_list,
)

# ---------------------------------------------------------------------------
# validate_name_list
# ---------------------------------------------------------------------------


def test_validate_name_list_valid():
    """A list of unique, non-blank strings should pass."""
    names = ["Alice", "Bob", "Charlie"]
    result = validate_name_list("test", names)
    assert result == ["Alice", "Bob", "Charlie"]


def test_validate_name_list_strips_whitespace():
    names = ["  Alice  ", "Bob"]
    result = validate_name_list("test", names)
    assert result == ["Alice", "Bob"]


def test_validate_name_list_blank_raises():
    with pytest.raises(ResourceValidationError, match="must not be blank"):
        validate_name_list("test", ["Alice", "", "Bob"])


def test_validate_name_list_non_string_raises():
    with pytest.raises(ResourceValidationError, match="must be a string"):
        validate_name_list("test", ["Alice", 123])


def test_validate_name_list_duplicate_raises():
    with pytest.raises(ResourceValidationError, match="duplicate name"):
        validate_name_list("test", ["Alice", "alice"])


def test_validate_name_list_empty_is_valid():
    result = validate_name_list("test", [])
    assert result == []


# ---------------------------------------------------------------------------
# load_names_from_root
# ---------------------------------------------------------------------------


def test_load_names_from_root_nonexistent_directory():
    """Loading from a nonexistent path should return an empty list."""
    result = load_names_from_root(Path("/nonexistent/path/to/nothing"))
    assert result == []


def test_load_names_from_root_reads_txt_files(tmp_path):
    """Should read all .txt files and return non-blank lines."""
    txt_file = tmp_path / "names.txt"
    txt_file.write_text("Alice\nBob\n\nCharlie\n")

    result = load_names_from_root(tmp_path)
    assert result == ["Alice", "Bob", "Charlie"]


def test_load_names_from_root_ignores_non_txt(tmp_path):
    """Non-.txt files should be ignored."""
    (tmp_path / "data.json").write_text('{"key": "value"}')
    (tmp_path / "names.txt").write_text("Alice\n")

    result = load_names_from_root(tmp_path)
    assert result == ["Alice"]


def test_load_names_from_root_multiple_files(tmp_path):
    """Names from multiple .txt files should be combined."""
    (tmp_path / "a.txt").write_text("Alice\n")
    (tmp_path / "b.txt").write_text("Bob\n")

    result = load_names_from_root(tmp_path)
    assert sorted(result) == ["Alice", "Bob"]


# ---------------------------------------------------------------------------
# BaseEventValidator - helper methods
# ---------------------------------------------------------------------------


def test_base_event_validator_no_errors():
    """A validator with no errors should not raise."""
    v = BaseEventValidator(set(), set(), set())
    v.raise_if_invalid()  # should not raise


def test_base_event_validator_raises_on_error():
    """A validator with errors should raise EventValidationError."""
    v = BaseEventValidator(set(), set(), set())
    v.error("path.to.field", "something is wrong")

    with pytest.raises(EventValidationError, match="something is wrong"):
        v.raise_if_invalid()


def test_base_event_validator_multiple_errors():
    """Multiple errors should all be included in the error message."""
    v = BaseEventValidator(set(), set(), set())
    v.error("path.a", "error one")
    v.error("path.b", "error two")

    with pytest.raises(EventValidationError) as exc_info:
        v.raise_if_invalid()

    message = str(exc_info.value)
    assert "error one" in message
    assert "error two" in message


def test_validate_optional_int_valid():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_int("test", {"count": 5}, "count")
    assert result == 5
    assert not v.errors


def test_validate_optional_int_missing_returns_none():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_int("test", {}, "count")
    assert result is None
    assert not v.errors


def test_validate_optional_int_boolean_rejected():
    """Booleans should not be accepted as integers."""
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_int("test", {"count": True}, "count")
    assert result is None
    assert len(v.errors) == 1
    assert "integer" in v.errors[0]


def test_validate_optional_int_below_minimum():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_int("test", {"count": -1}, "count", minimum=0)
    assert result is None
    assert len(v.errors) == 1


def test_validate_optional_bool_valid():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_bool("test", {"flag": True}, "flag")
    assert result is True
    assert not v.errors


def test_validate_optional_bool_string_rejected():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_bool("test", {"flag": "true"}, "flag")
    assert result is None
    assert len(v.errors) == 1


def test_validate_optional_string_valid():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_string("test", {"name": "hello"}, "name")
    assert result == "hello"
    assert not v.errors


def test_validate_optional_string_blank_rejected():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_optional_string("test", {"name": "  "}, "name", allow_blank=False)
    assert result is None
    assert len(v.errors) == 1


def test_validate_enum_string_valid():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_enum_string("test", {"rarity": "common"}, "rarity", {"common", "rare"})
    assert result == "common"
    assert not v.errors


def test_validate_enum_string_invalid():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_enum_string("test", {"rarity": "mythic"}, "rarity", {"common", "rare"})
    assert result is None
    assert len(v.errors) == 1


def test_validate_name_list_unknown_name():
    v = BaseEventValidator(breed_names={"poodle", "labrador"}, mutation_names=set(), event_names=set())
    v._validate_name_list("test", {"breeds": ["poodle", "unknown"]}, "breeds", v.breed_names)
    assert len(v.errors) == 1
    assert "unknown" in v.errors[0]


def test_validate_int_list_valid():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_int_list("test", {"ages": [1, 2, 3]}, "ages")
    assert result == [1, 2, 3]
    assert not v.errors


def test_validate_int_list_not_a_list():
    v = BaseEventValidator(set(), set(), set())
    result = v._validate_int_list("test", {"ages": "bad"}, "ages")
    assert result is None
    assert len(v.errors) == 1


def test_validate_int_list_boolean_in_list():
    """Booleans inside an int list should be rejected."""
    v = BaseEventValidator(set(), set(), set())
    v._validate_int_list("test", {"ages": [1, True, 3]}, "ages")
    assert len(v.errors) == 1
