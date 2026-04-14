"""
Session/auth helpers for the Flask web layer.

Provides:

- ``login_required`` / ``server_required`` decorators
- ``get_current_user_id`` / ``get_current_server_id`` session accessors
- Centralized ownership helpers (``require_pooch_owner``, ``require_kennel_owner``,
  ``require_owner``) that every mutation route should call before touching state.

The ownership helpers return the hydrated ORM object on success and abort
with a 403 or 404 on failure — so a route can use them directly::

    pooch = require_pooch_owner(pooch_id)
    # ... safe to mutate from here
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
# These are the central authorization choke points for the web layer. Every
# write route that mutates pooch/kennel/owner state MUST call one of these
# before touching the database. They abort with 401/403/404 as appropriate
# and never leak sensitive data.


def _require_logged_in() -> int:
    uid = get_current_user_id()
    if uid is None:
        abort(401, description="You must be logged in.")
    return uid


def require_pooch_owner(pooch_id: int) -> Any:
    """
    Verify that the current user owns the pooch with ``pooch_id``.

    Returns the hydrated Pooch ORM object on success. Aborts with:
    - 401 if not logged in
    - 404 if the pooch doesn't exist
    - 403 if the current user does not own it
    """
    from src.database import get_pooch_by_id
    from src.web.async_utils import run_async

    user_id = _require_logged_in()
    pooch = run_async(get_pooch_by_id(int(pooch_id)))
    if pooch is None:
        abort(404, description="Pooch not found.")
    if int(pooch.owner_discord_id or 0) != int(user_id):
        abort(403, description="You don't own that pooch.")
    return pooch


def require_kennel_owner(kennel_id: int) -> Any:
    """
    Verify that the current user owns the kennel with ``kennel_id``.

    Returns the hydrated Kennel ORM object on success.
    """
    from src.database import get_kennel_by_id
    from src.web.async_utils import run_async

    user_id = _require_logged_in()
    kennel = run_async(get_kennel_by_id(int(kennel_id)))
    if kennel is None:
        abort(404, description="Kennel not found.")
    if int(kennel.owner_discord_id or 0) != int(user_id):
        abort(403, description="You don't own that kennel.")
    return kennel


def require_owner(owner_discord_id: int) -> int:
    """
    Assert that ``owner_discord_id`` matches the current session user.
    Returns the discord id on success.
    """
    user_id = _require_logged_in()
    if int(owner_discord_id) != int(user_id):
        abort(403, description="You can only act on your own account.")
    return user_id


def require_server_visible_pooch(pooch_id: int) -> Any:
    """
    Return the pooch if the current user is allowed to view its private data:
    owner of the pooch, OR the pooch's owner is registered to the currently
    selected server. Aborts 403 otherwise.
    """
    from src.database import get_owner_server, get_pooch_by_id
    from src.web.async_utils import run_async

    user_id = _require_logged_in()
    pooch = run_async(get_pooch_by_id(int(pooch_id)))
    if pooch is None:
        abort(404, description="Pooch not found.")
    owner_id = int(pooch.owner_discord_id or 0)
    if owner_id == int(user_id):
        return pooch

    server_id = get_current_server_id()
    if server_id is None or owner_id == 0:
        abort(403, description="You cannot view that pooch.")

    # Both viewer and pooch owner must share the current server.
    viewer_member = run_async(get_owner_server(int(server_id), int(user_id)))
    target_member = run_async(get_owner_server(int(server_id), owner_id))
    if viewer_member is None or target_member is None:
        abort(403, description="You cannot view that pooch.")
    return pooch
