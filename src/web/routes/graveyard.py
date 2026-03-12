from flask import Blueprint, render_template

from src.web.auth_utils import login_required

graveyard_bp = Blueprint("graveyard", __name__)


@graveyard_bp.route("/")
@login_required
def church():
    """The church hub — entry point for church-related pages."""
    return render_template("church.html")


@graveyard_bp.route("/graveyard")
@login_required
def graveyard():
    """View the graveyard — all deceased pooches buried by the current user."""
    return render_template("graveyard.html")
