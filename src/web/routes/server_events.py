from flask import Blueprint, g, render_template

from src.web.auth_utils import server_required

server_events_bp = Blueprint("server_events", __name__)


@server_events_bp.route("/")
@server_required
def server_events_list():
    """View the active server event for the current server."""
    return render_template(
        "server_events/list.html",
        server_id=g.current_server_id,
        server_name=g.current_server_name,
    )
