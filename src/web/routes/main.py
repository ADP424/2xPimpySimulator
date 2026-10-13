from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, session, url_for

from src.web.async_utils import run_async
from src.web.auth_utils import get_current_user_id, login_required, server_required
from src.web.discord_oauth import get_guild_dicts_from_session

main_bp = Blueprint("main", __name__)

# Same as the bot's /town greeting
_SEASON_EMOJIS = {
    "spring": "🌸🌿",
    "summer": "☀️🌻",
    "autumn": "🍂🍁",
    "winter": "❄️⛄",
}


def _get_known_server_ids() -> set[int]:
    """Return the set of server IDs that exist in the game database."""
    from src.game import list_servers

    servers = run_async(list_servers())
    return {int(s.discord_id) for s in servers}


def _filter_guilds_to_known_servers(guilds: list[dict]) -> list[dict]:
    """Filter the user's guild list down to servers known by the bot."""

    known_ids = _get_known_server_ids()
    return [g for g in guilds if int(g.get("id", 0)) in known_ids]


@main_bp.route("/")
def index():
    """Landing page."""

    if "discord_id" in session:
        return redirect(url_for("main.home"))
    return render_template("index.html")


@main_bp.route("/home")
@login_required
def home():
    """User's home page with account info and recent owner_events."""

    discord_id = get_current_user_id()

    guilds = _filter_guilds_to_known_servers(get_guild_dicts_from_session())
    server_ids = [int(g["id"]) for g in guilds]

    return render_template(
        "home.html",
        discord_id=discord_id,
        username=session.get("discord_username"),
        avatar_url=session.get("discord_avatar_url"),
        server_ids=server_ids,
        guilds=guilds,
    )


@main_bp.route("/servers")
@login_required
def select_server():
    """Server selection page."""

    available_servers = _filter_guilds_to_known_servers(get_guild_dicts_from_session())

    return render_template(
        "select_server.html",
        servers=available_servers,
        current_server_id=session.get("current_server_id"),
        current_server_name=session.get("current_server_name"),
    )


@main_bp.route("/servers/<int:server_id>/select", methods=["POST"])
@login_required
def set_server(server_id: int):
    """Set the currently active server."""

    available_servers = _filter_guilds_to_known_servers(get_guild_dicts_from_session())

    server = next((g for g in available_servers if int(g["id"]) == server_id), None)
    if server is None:
        return "You are not a member of this server (or the bot has not interacted with it).", 403

    from src.game import get_or_create_owner, get_server

    # Ensure the server exists in the DB (should be true if it's in available_servers)
    if run_async(get_server(server_id)) is None:
        return "Server not initialized by the bot yet.", 404

    session["current_server_id"] = server_id
    session["current_server_name"] = server["name"]

    # Ensure owner exists for this server

    discord_id = get_current_user_id()
    if discord_id is not None:
        run_async(get_or_create_owner(server_id, discord_id))

    return redirect(url_for("main.town"))


@main_bp.route("/town")
@server_required
def town():
    """Town page for the currently selected server."""
    from src.game import get_season

    season = run_async(get_season())
    return render_template(
        "town.html",
        server_id=g.current_server_id,
        server_name=g.current_server_name,
        season=season,
        season_emojis=_SEASON_EMOJIS.get((season or "").lower(), ""),
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Dashboard showing a live day-change event feed."""

    servers = _filter_guilds_to_known_servers(get_guild_dicts_from_session())
    server_ids = [int(s["id"]) for s in servers]

    return render_template(
        "dashboard.html",
        servers=servers,
        server_ids=server_ids,
        current_server_id=session.get("current_server_id"),
        current_server_name=session.get("current_server_name"),
    )
