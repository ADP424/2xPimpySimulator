from flask import Blueprint, g, render_template

from web.auth_utils import server_required

info_bp = Blueprint("info", __name__)


@info_bp.route("/clinic")
@server_required
def veterinary_clinic():
    """Veterinary clinic - info hub for breeds and mutations."""

    return render_template(
        "info/clinic.html",
        server_name=g.current_server_name,
    )


@info_bp.route("/breeds")
@server_required
def breeds_list():
    """List all breeds."""

    return render_template("info/breeds.html")


@info_bp.route("/breeds/<int:breed_id>")
@server_required
def breed_detail(breed_id: int):
    """View details about a specific breed."""

    return render_template(
        "info/breed_detail.html",
        breed_id=breed_id,
    )


@info_bp.route("/mutations")
@server_required
def mutations_list():
    """List all mutations."""

    return render_template("info/mutations.html")


@info_bp.route("/mutations/<int:mutation_id>")
@server_required
def mutation_detail(mutation_id: int):
    """View details about a specific mutation."""

    return render_template(
        "info/mutation_detail.html",
        mutation_id=mutation_id,
    )
