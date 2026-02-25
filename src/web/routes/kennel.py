from flask import Blueprint, render_template

from web.auth_utils import get_current_user_id, login_required

kennel_bp = Blueprint("kennel", __name__)


@kennel_bp.route("/")
@login_required
def kennels_list():
    """List all kennels owned by the user."""

    return render_template(
        "kennel/list.html",
        discord_id=get_current_user_id(),
    )


@kennel_bp.route("/<int:kennel_id>")
@login_required
def kennel_detail(kennel_id: int):
    """View a specific kennel and its pooches."""

    return render_template(
        "kennel/detail.html",
        kennel_id=kennel_id,
    )


@kennel_bp.route("/<int:kennel_id>/breed")
@login_required
def breeding_interface(kennel_id: int):
    """Breeding interface for a kennel."""

    return render_template(
        "kennel/breed.html",
        kennel_id=kennel_id,
    )
