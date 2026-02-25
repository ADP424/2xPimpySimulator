import secrets

from flask import Blueprint, current_app, redirect, request, session, url_for

from web.discord_oauth import (
    exchange_code,
    get_oauth_url,
    get_user,
    get_user_guilds,
    store_user_in_session,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    """Initiate Discord OAuth flow."""

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    next_url = request.args.get("next")
    if next_url:
        session["next_url"] = next_url

    return redirect(get_oauth_url(state))


@auth_bp.route("/callback")
def callback():
    """Handle Discord OAuth callback."""

    state = request.args.get("state")
    if state != session.get("oauth_state"):
        return "Invalid state parameter", 400

    error = request.args.get("error")
    if error:
        return f"OAuth error: {error}", 400

    code = request.args.get("code")
    if not code:
        return "No authorization code provided", 400

    try:
        tokens = exchange_code(code)
        access_token = tokens["access_token"]

        user = get_user(access_token)
        guilds = get_user_guilds(access_token)

        # Clear any existing session data first to prevent contamination
        session.clear()

        store_user_in_session(user, guilds, access_token)

        next_url = session.pop("next_url", None) or request.args.get("next")
        if next_url:
            return redirect(next_url)

        return redirect(url_for("main.home"))

    except Exception as exc:
        current_app.logger.error(f"OAuth callback error: {exc}", exc_info=True)
        return f"Authentication failed: {str(exc)}", 500


@auth_bp.route("/logout")
def logout():
    """Log out the current user."""

    session.clear()
    return redirect(url_for("main.index"))
