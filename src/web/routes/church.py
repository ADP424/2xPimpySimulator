from flask import Blueprint, render_template

from src.web.auth_utils import login_required, server_required

church_bp = Blueprint("church", __name__)


@church_bp.route("/")
@server_required
def church_hub():
    """Church hub — graveyard and basement."""
    return render_template("church.html")


@church_bp.route("/basement")
@login_required
def basement():
    """Church basement — sacrifice, summon, and gaze into hell."""
    from src.game import describe_ritual_costs

    return render_template("church/basement.html", ritual_costs=describe_ritual_costs())


@church_bp.route("/beg")
@server_required
def beg():
    """Begging page — ask the church for spare change."""
    return render_template("church/beg.html")
