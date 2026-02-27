from flask import Blueprint, jsonify, request

from web.async_utils import run_async
from web.auth_utils import (
    get_current_server_id,
    get_current_user_id,
    login_required,
    server_required,
)
from web.serializers import (
    serialize_breed,
    serialize_kennel,
    serialize_mutation,
    serialize_owner,
    serialize_pooch,
    serialize_vendor,
)

api_bp = Blueprint("api", __name__)


@api_bp.route("/owner")
@server_required
def get_owner():
    """Get the current user's owner info for the current server."""
    from game import get_or_create_owner

    discord_id = get_current_user_id()
    server_id = get_current_server_id()

    owner = run_async(get_or_create_owner(server_id, discord_id))
    return jsonify(serialize_owner(owner))


@api_bp.route("/kennels")
@login_required
def get_kennels():
    """Get all kennels owned by the current user."""
    from game import list_owner_kennels

    discord_id = get_current_user_id()
    kennels = run_async(list_owner_kennels(discord_id))
    return jsonify([serialize_kennel(k) for k in kennels])


@api_bp.route("/kennels/<int:kennel_id>/pooches")
@login_required
def get_kennel_pooches(kennel_id: int):
    """Get all pooches in a specific kennel."""
    from game import list_kennel_pooches

    try:
        pooches = run_async(list_kennel_pooches(kennel_id))
        return jsonify([serialize_pooch(p) for p in pooches])
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>")
@login_required
def get_pooch(pooch_id: int):
    """Get detailed info about a specific pooch."""
    from game import get_pooch_by_id

    try:
        pooch = run_async(get_pooch_by_id(pooch_id))
        return jsonify(serialize_pooch(pooch))
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>/family")
@login_required
def get_pooch_family(pooch_id: int):
    """Get the family of a specific pooch."""
    from game import get_pooch_family

    try:
        family = run_async(get_pooch_family(pooch_id))
        return jsonify(
            {
                "parents": [serialize_pooch(p, include_relations=False) for p in family.get("parents", [])],
                "children": [serialize_pooch(p, include_relations=False) for p in family.get("children", [])],
                "siblings": [serialize_pooch(p, include_relations=False) for p in family.get("siblings", [])],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>/buy-price")
@login_required
def get_pooch_buy_price(pooch_id: int):
    """Get the buy price of a pooch, optionally from a vendor."""
    from game import get_pooch_buy_price

    vendor_id = request.args.get("vendor_id", type=int)

    try:
        price = run_async(get_pooch_buy_price(pooch_id, vendor_id))
        return jsonify({"price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>/sell-price")
@login_required
def get_pooch_sell_price(pooch_id: int):
    """Get the sell price of a pooch, optionally to a vendor."""
    from game import get_pooch_sell_price

    vendor_id = request.args.get("vendor_id", type=int)

    try:
        price = run_async(get_pooch_sell_price(pooch_id, vendor_id))
        return jsonify({"price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/breed", methods=["POST"])
@login_required
def breed_pooches():
    """Breed two pooches."""
    from game import breed_pooches as game_breed_pooches
    from game import get_pooch_by_id

    data = request.json
    first_pooch_id = data.get("first_pooch_id")
    second_pooch_id = data.get("second_pooch_id")

    if not first_pooch_id or not second_pooch_id:
        return jsonify({"error": "Both pooch IDs are required"}), 400

    try:
        new_pooch_ids = run_async(game_breed_pooches(first_pooch_id, second_pooch_id))
        new_pooches = [run_async(get_pooch_by_id(pid)) for pid in new_pooch_ids]
        return jsonify(
            {
                "success": True,
                "new_pooch_ids": new_pooch_ids,
                "new_pooches": [serialize_pooch(p) for p in new_pooches],
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/incest-check")
@login_required
def check_incest():
    """Check incest level between two pooches."""
    from game import calculate_incest_level

    first_id = request.args.get("first_pooch_id", type=int)
    second_id = request.args.get("second_pooch_id", type=int)

    if not first_id or not second_id:
        return jsonify({"error": "Both pooch IDs are required"}), 400

    try:
        level = run_async(calculate_incest_level(first_id, second_id))
        return jsonify({"incest_level": level})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/vendors")
@server_required
def get_vendors():
    """Get all vendors for the current server."""
    from game import list_server_vendors

    server_id = get_current_server_id()
    vendors = run_async(list_server_vendors(server_id))
    return jsonify([serialize_vendor(v) for v in vendors])


@api_bp.route("/vendors/<int:vendor_id>")
@login_required
def get_vendor(vendor_id: int):
    """Get info about a specific vendor."""
    from game import get_vendor_by_id

    try:
        vendor = run_async(get_vendor_by_id(vendor_id))
        return jsonify(serialize_vendor(vendor))
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/vendors/<int:vendor_id>/pooches")
@login_required
def get_vendor_pooches(vendor_id: int):
    """Get all pooches for sale by a vendor."""
    from game import get_pooch_buy_price, list_vendor_pooches

    try:
        pooches = run_async(list_vendor_pooches(vendor_id))
        result = []
        for p in pooches:
            pooch_data = serialize_pooch(p)
            pooch_data["buy_price"] = run_async(get_pooch_buy_price(p.id, vendor_id))
            result.append(pooch_data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/vendors/<int:vendor_id>/buy/<int:pooch_id>", methods=["POST"])
@login_required
def buy_pooch(vendor_id: int, pooch_id: int):
    """Buy a pooch from a vendor."""
    from game import buy_pooch as game_buy_pooch

    discord_id = get_current_user_id()

    try:
        success, message = run_async(game_buy_pooch(discord_id, vendor_id, pooch_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/graveyard")
@login_required
def get_graveyard():
    """Get all deceased pooches buried by the current user."""
    from game import list_graveyard_pooches

    discord_id = get_current_user_id()
    rows = run_async(list_graveyard_pooches(discord_id))
    result = []
    for pooch, buried_at in rows:
        pooch_data = serialize_pooch(pooch)
        pooch_data["buried_at"] = buried_at.isoformat() if buried_at else None
        result.append(pooch_data)
    return jsonify(result)


@api_bp.route("/breeds")
@login_required
def get_breeds():
    """Get all breeds."""
    from game import list_all_breeds

    breeds = run_async(list_all_breeds())
    return jsonify([serialize_breed(b) for b in breeds])


@api_bp.route("/breeds/<int:breed_id>")
@login_required
def get_breed(breed_id: int):
    """Get a single breed by ID."""
    from game import list_all_breeds

    breeds = run_async(list_all_breeds())
    for b in breeds:
        if int(getattr(b, "id", -1)) == int(breed_id):
            return jsonify(serialize_breed(b))
    return jsonify({"error": "Breed not found"}), 404


@api_bp.route("/mutations")
@login_required
def get_mutations():
    """Get all mutations."""
    from game import list_all_mutations

    mutations = run_async(list_all_mutations())
    return jsonify([serialize_mutation(m) for m in mutations])


@api_bp.route("/mutations/<int:mutation_id>")
@login_required
def get_mutation(mutation_id: int):
    """Get a single mutation by ID."""
    from game import list_all_mutations

    mutations = run_async(list_all_mutations())
    for m in mutations:
        if int(getattr(m, "id", -1)) == int(mutation_id):
            return jsonify(serialize_mutation(m))
    return jsonify({"error": "Mutation not found"}), 404
