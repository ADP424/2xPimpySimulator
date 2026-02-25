from flask import Blueprint, g, render_template

from web.auth_utils import server_required

vendor_bp = Blueprint("vendor", __name__)


@vendor_bp.route("/")
@server_required
def vendors_list():
    """List all vendors in the current server."""

    return render_template(
        "vendor/list.html",
        server_id=g.current_server_id,
        server_name=g.current_server_name,
    )


@vendor_bp.route("/<int:vendor_id>")
@server_required
def vendor_detail(vendor_id: int):
    """View a specific vendor and their pooches for sale."""

    return render_template(
        "vendor/detail.html",
        vendor_id=vendor_id,
        server_name=g.current_server_name,
    )
