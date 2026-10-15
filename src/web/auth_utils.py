"""
Session/auth helpers for the Flask web layer.

Provides:

- ``login_required`` / ``server_required`` decorators
- ``get_current_user_id`` / ``get_current_server_id`` session accessors
- Ownership checks (``require_pooch_owner``, ``require_kennel_owner``) that every route acting on a pooch or
  kennel calls first; they abort with a 401, 403 or 404 on failure.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import abort, g, redirect, request, session, url_for


def login_required(f: Callable) -> Callable:
    """Decorator to require authentication."""

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "discord_id" not in session:
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def server_required(f: Callable) -> Callable:
    """Decorator to require a server to be selected."""

    @wraps(f)
    @login_required
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "current_server_id" not in session:
            return redirect(url_for("main.select_server"))
        g.current_server_id = session["current_server_id"]
        g.current_server_name = session.get("current_server_name", "Unknown Server")
        return f(*args, **kwargs)

    return decorated_function


def get_current_user_id() -> int | None:
    """Get the current user's Discord ID from the session."""
    return session.get("discord_id")


def get_current_server_id() -> int | None:
    """Get the currently selected server's Discord ID from the session."""
    return session.get("current_server_id")


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------
#
# The web layer's authorization choke points. Every route that acts on a pooch or kennel MUST call one of these
# first; the ownership rule itself lives in the game layer. Viewing is open to everyone (the serializers hide
# private data), so only actions need these. They abort with 401/403/404 and never leak data.


def _require_logged_in() -> int:
    uid = get_current_user_id()
    if uid is None:
        abort(401, description="You must be logged in.")
    return uid


def require_pooch_owner(pooch_id: int) -> None:
    """Abort with 401 if not logged in, 404 if the pooch doesn't exist, or 403 if the current user doesn't own it."""
    from src.game import owns_pooch
    from src.web.async_utils import run_async

    owns = run_async(owns_pooch(_require_logged_in(), int(pooch_id)))
    if owns is None:
        abort(404, description="Pooch not found.")
    if not owns:
        abort(403, description="That's not your pooch.")


def require_kennel_owner(kennel_id: int) -> None:
    """Abort with 401 if not logged in, 404 if the kennel doesn't exist, or 403 if the current user doesn't own it."""
    from src.game import owns_kennel
    from src.web.async_utils import run_async

    owns = run_async(owns_kennel(_require_logged_in(), int(kennel_id)))
    if owns is None:
        abort(404, description="Kennel not found.")
    if not owns:
        abort(403, description="That's not your kennel.")
