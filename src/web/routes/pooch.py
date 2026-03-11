from flask import Blueprint, render_template

from src.web.auth_utils import login_required

pooch_bp = Blueprint("pooch", __name__)


@pooch_bp.route("/<int:pooch_id>")
@login_required
def pooch_detail(pooch_id: int):
    """View detailed info about a specific pooch."""

    return render_template(
        "pooch/detail.html",
        pooch_id=pooch_id,
    )
