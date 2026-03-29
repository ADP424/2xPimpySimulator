from flask import Blueprint, render_template

from src.web.auth_utils import server_required

construction_bp = Blueprint("construction", __name__)


@construction_bp.route("/")
@server_required
def construction():
    """Construction company — buy and upgrade kennels."""

    return render_template("construction/index.html")
