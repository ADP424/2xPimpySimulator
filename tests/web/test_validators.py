"""Tests for src/web/validators.py."""

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest

from src.web.validators import (
    clean_display_name,
    coerce_bounded_int,
    coerce_id,
    coerce_int,
    coerce_non_negative_int,
    coerce_positive_int,
    validate_one_of,
)


@pytest.fixture
def app_ctx():
    """A Flask app context so flask.abort can work."""
    app = Flask(__name__)
    with app.test_request_context():
        yield


def test_coerce_int_happy(app_ctx):
    assert coerce_int("42") == 42
    assert coerce_int(42) == 42


def test_coerce_int_rejects_missing(app_ctx):
    with pytest.raises(BadRequest):
        coerce_int(None)
    with pytest.raises(BadRequest):
        coerce_int("")


def test_coerce_int_rejects_non_int(app_ctx):
    with pytest.raises(BadRequest):
        coerce_int("abc")


def test_coerce_positive_int(app_ctx):
    assert coerce_positive_int(5) == 5
    with pytest.raises(BadRequest):
        coerce_positive_int(0)
    with pytest.raises(BadRequest):
        coerce_positive_int(-1)


def test_coerce_non_negative_int(app_ctx):
    assert coerce_non_negative_int(0) == 0
    assert coerce_non_negative_int(3) == 3
    with pytest.raises(BadRequest):
        coerce_non_negative_int(-1)


def test_coerce_id(app_ctx):
    assert coerce_id(7) == 7
    with pytest.raises(BadRequest):
        coerce_id(0)


def test_coerce_bounded_int(app_ctx):
    assert coerce_bounded_int(5, minimum=0, maximum=10) == 5
    with pytest.raises(BadRequest):
        coerce_bounded_int(-1, minimum=0, maximum=10)
    with pytest.raises(BadRequest):
        coerce_bounded_int(11, minimum=0, maximum=10)


def test_clean_display_name_happy(app_ctx):
    assert clean_display_name("  Rex  ") == "Rex"
    assert clean_display_name("Mr   Bojangles") == "Mr Bojangles"


def test_clean_display_name_rejects_empty(app_ctx):
    with pytest.raises(BadRequest):
        clean_display_name("")
    with pytest.raises(BadRequest):
        clean_display_name("   ")
    with pytest.raises(BadRequest):
        clean_display_name(None)


def test_clean_display_name_rejects_control_chars(app_ctx):
    with pytest.raises(BadRequest):
        clean_display_name("Rex\x00")
    with pytest.raises(BadRequest):
        clean_display_name("Rex\x07")


def test_clean_display_name_rejects_html(app_ctx):
    with pytest.raises(BadRequest):
        clean_display_name("<script>")
    with pytest.raises(BadRequest):
        clean_display_name("Rex>")


def test_clean_display_name_max_length(app_ctx):
    with pytest.raises(BadRequest):
        clean_display_name("x" * 101, max_length=100)


def test_clean_display_name_min_length(app_ctx):
    with pytest.raises(BadRequest):
        clean_display_name("x", min_length=3)


def test_validate_one_of(app_ctx):
    assert validate_one_of("a", ["a", "b"]) == "a"
    with pytest.raises(BadRequest):
        validate_one_of("c", ["a", "b"])
    with pytest.raises(BadRequest):
        validate_one_of(None, ["a", "b"])
