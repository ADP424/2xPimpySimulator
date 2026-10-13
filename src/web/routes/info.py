from flask import Blueprint, g, render_template

from src.web.auth_utils import server_required

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


@info_bp.route("/clinic/patients")
@server_required
def patients_list():
    """Patient Room: pick one of your pooches to treat or diagnose."""

    return render_template("info/patients.html")


@info_bp.route("/clinic/patients/<int:pooch_id>")
@server_required
def patient_detail(pooch_id: int):
    """Treat and diagnose one of your pooches."""

    return render_template(
        "info/patient.html",
        pooch_id=pooch_id,
    )


@info_bp.route("/injuries")
@server_required
def injuries_list():
    """List all injuries."""

    return render_template("info/injuries.html")


@info_bp.route("/injuries/<int:injury_id>")
@server_required
def injury_detail(injury_id: int):
    """View details about a specific injury."""

    return render_template(
        "info/injury_detail.html",
        injury_id=injury_id,
    )


@info_bp.route("/diseases")
@server_required
def diseases_list():
    """List all diseases."""

    return render_template("info/diseases.html")


@info_bp.route("/diseases/<int:disease_id>")
@server_required
def disease_detail(disease_id: int):
    """View details about a specific disease."""

    return render_template(
        "info/disease_detail.html",
        disease_id=disease_id,
    )
