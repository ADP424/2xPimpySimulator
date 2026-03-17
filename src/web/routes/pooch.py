from flask import Blueprint, render_template

from web.async_utils import run_async
from web.auth_utils import login_required

pooch_bp = Blueprint("pooch", __name__)


@pooch_bp.route("/<int:pooch_id>/embed")
def pooch_embed(pooch_id: int):
    """Public endpoint for Discord/social link embeds (Open Graph meta tags)."""
    from game import get_pooch_by_id

    pooch_meta = None
    try:
        pooch = run_async(get_pooch_by_id(pooch_id))
        breeds = ", ".join(b.breed.name for b in pooch.breeds) if pooch.breeds else "Unknown"
        mutations = ", ".join(m.name for m in pooch.mutations) if pooch.mutations else "None"
        sex = "Female" if pooch.sex == "female" else "Male"
        status = pooch.status.capitalize() if pooch.status else "Unknown"
        pooch_meta = {
            "title": f"{pooch.name} - Pooch Breeder",
            "description": f"{sex} | Age: {pooch.age} days | {status}\nBreeds: {breeds}\nMutations: {mutations}",
            "url": f"/pooch/{pooch_id}",
        }
    except Exception:
        pooch_meta = {
            "title": "Pooch Not Found - Pooch Breeder",
            "description": "This pooch could not be found.",
            "url": f"/pooch/{pooch_id}",
        }

    return render_template(
        "pooch/embed.html",
        pooch_id=pooch_id,
        pooch_meta=pooch_meta,
    )


@pooch_bp.route("/<int:pooch_id>")
@login_required
def pooch_detail(pooch_id: int):
    """View detailed info about a specific pooch."""

    return render_template(
        "pooch/detail.html",
        pooch_id=pooch_id,
    )


@pooch_bp.route("/<int:pooch_id>/family-tree")
@login_required
def pooch_family_tree(pooch_id: int):
    """View the family tree of a specific pooch."""

    return render_template(
        "pooch/family_tree.html",
        pooch_id=pooch_id,
    )
