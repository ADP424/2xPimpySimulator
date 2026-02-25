from functools import wraps
from typing import Any, Callable

from flask import g, redirect, request, session, url_for


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
