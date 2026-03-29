from flask import Blueprint, render_template

from src.web.auth_utils import server_required

park_bp = Blueprint("park", __name__)


@park_bp.route("/")
@server_required
def park():
    """Park — attract stray pooches."""
    return render_template("park.html")
