from flask import Blueprint, g, render_template

from src.web.auth_utils import server_required

auction_bp = Blueprint("auction", __name__)


@auction_bp.route("/")
@server_required
def auction_hub():
    """Auction house hub — browse sales and bounties."""

    return render_template(
        "auction/hub.html",
        server_id=g.current_server_id,
        server_name=g.current_server_name,
    )


@auction_bp.route("/sale/<int:listing_id>")
@server_required
def sale_detail(listing_id: int):
    """View a specific sale listing."""

    return render_template(
        "auction/sale_detail.html",
        listing_id=listing_id,
        server_name=g.current_server_name,
    )


@auction_bp.route("/bounty/<int:listing_id>")
@server_required
def bounty_detail(listing_id: int):
    """View a specific bounty listing."""

    return render_template(
        "auction/bounty_detail.html",
        listing_id=listing_id,
        server_id=g.current_server_id,
        server_name=g.current_server_name,
    )


@auction_bp.route("/create-sale")
@server_required
def create_sale():
    """Form to create a new sale listing."""

    return render_template(
        "auction/create_sale.html",
        server_name=g.current_server_name,
    )


@auction_bp.route("/create-bounty")
@server_required
def create_bounty():
    """Form to create a new bounty listing."""

    return render_template(
        "auction/create_bounty.html",
        server_name=g.current_server_name,
    )
