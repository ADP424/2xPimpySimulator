from flask import Blueprint, g, render_template

from src.web.auth_utils import server_required

auction_bp = Blueprint("auction", __name__)


@auction_bp.route("/")
@server_required
def auction_list():
    """Auction house — sale listings and bounties for the current server."""
    return render_template(
        "auction/list.html",
        server_id=g.current_server_id,
        server_name=g.current_server_name,
    )
