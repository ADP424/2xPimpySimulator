from flask import Blueprint, g, render_template

from src.web.auth_utils import server_required

events_bp = Blueprint("events", __name__)


@events_bp.route("/")
@server_required
def owner_events():
    """Your owner events — respond to pending ones and read your history."""

    return render_template(
        "events/owner.html",
        server_name=g.current_server_name,
    )
