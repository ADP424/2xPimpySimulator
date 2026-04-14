"""
Lightweight input validators for the Flask web layer.

These are small helpers that normalize and validate request input. They
abort with a 400 on failure rather than returning a tuple, so routes can
just write::

    data = request.get_json(silent=True) or {}
    name = clean_display_name(data.get("name"), field="name")

and rely on Flask to short-circuit on bad input.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from flask import abort


class ValidationError(ValueError):
    """Raised for user-friendly validation errors."""

    def __init__(self, message: str, *, status: int = 400):
        super().__init__(message)
        self.status = status


# Matches a run of any whitespace (spaces, tabs, newlines).
_WHITESPACE_RE = re.compile(r"\s+")

# Control characters that should never appear in a user-facing name.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def coerce_int(value: Any, *, field: str = "value") -> int:
    """Return ``value`` as an ``int`` or abort 400."""
    if value is None or value == "":
        abort(400, description=f"{field} is required.")
    try:
        return int(value)
    except TypeError, ValueError:
        abort(400, description=f"{field} must be an integer.")


def coerce_positive_int(value: Any, *, field: str = "value") -> int:
    n = coerce_int(value, field=field)
    if n <= 0:
        abort(400, description=f"{field} must be positive.")
    return n


def coerce_non_negative_int(value: Any, *, field: str = "value") -> int:
    n = coerce_int(value, field=field)
    if n < 0:
        abort(400, description=f"{field} must be non-negative.")
    return n


def coerce_id(value: Any, *, field: str = "id") -> int:
    """Id must be positive integer; 0 is not valid."""
    return coerce_positive_int(value, field=field)


def coerce_bounded_int(value: Any, *, minimum: int, maximum: int, field: str = "value") -> int:
    n = coerce_int(value, field=field)
    if n < minimum or n > maximum:
        abort(400, description=f"{field} must be between {minimum} and {maximum}.")
    return n


def clean_display_name(
    raw: Any,
    *,
    max_length: int = 100,
    min_length: int = 1,
    field: str = "name",
) -> str:
    """
    Normalize and validate a user-provided display name.

    - Accepts anything stringish.
    - Strips leading/trailing whitespace.
    - Collapses runs of internal whitespace to a single space.
    - Rejects names containing control characters.
    - Rejects names that look like raw HTML tags (any ``<`` / ``>``).
    - Enforces ``min_length`` / ``max_length``.
    - Aborts 400 with a descriptive message on failure.
    """
    if raw is None:
        abort(400, description=f"{field} is required.")
    if not isinstance(raw, str):
        raw = str(raw)

    normalized = _WHITESPACE_RE.sub(" ", raw).strip()

    if not normalized:
        abort(400, description=f"{field} is required.")

    if _CONTROL_RE.search(normalized):
        abort(400, description=f"{field} contains invalid characters.")

    if "<" in normalized or ">" in normalized:
        abort(400, description=f"{field} cannot contain '<' or '>'.")

    if len(normalized) < min_length:
        abort(400, description=f"{field} is too short (min {min_length} characters).")

    if len(normalized) > max_length:
        abort(400, description=f"{field} is too long (max {max_length} characters).")

    return normalized


def validate_one_of(value: Any, choices: Iterable[str], *, field: str = "value") -> str:
    allowed = list(choices)
    if value is None:
        abort(400, description=f"{field} is required.")
    s = str(value)
    if s not in allowed:
        abort(400, description=f"{field} must be one of: {', '.join(allowed)}.")
    return s
