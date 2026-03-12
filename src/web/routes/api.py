from flask import Blueprint, jsonify, request

from src.web.async_utils import run_async
from src.web.auth_utils import (
    get_current_server_id,
    get_current_user_id,
    login_required,
    server_required,
)
from src.web.serializers import (
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
    from src.game import get_or_create_owner

    discord_id = get_current_user_id()
    server_id = get_current_server_id()

    owner = run_async(get_or_create_owner(server_id, discord_id))
    return jsonify(serialize_owner(owner))


@api_bp.route("/kennels")
@login_required
def get_kennels():
    """Get all kennels owned by the current user."""
    from src.game import list_owner_kennels

    discord_id = get_current_user_id()
    kennels = run_async(list_owner_kennels(discord_id))
    return jsonify([serialize_kennel(k) for k in kennels])


@api_bp.route("/kennels/<int:kennel_id>/pooches")
@login_required
def get_kennel_pooches(kennel_id: int):
    """Get all pooches in a specific kennel."""
    from src.game import list_kennel_pooches

    try:
        pooches = run_async(list_kennel_pooches(kennel_id))
        return jsonify([serialize_pooch(p) for p in pooches])
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>")
@login_required
def get_pooch(pooch_id: int):
    """Get detailed info about a specific pooch."""
    from src.game import get_pooch_by_id

    try:
        pooch = run_async(get_pooch_by_id(pooch_id))
        return jsonify(serialize_pooch(pooch))
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>/family")
@login_required
def get_pooch_family(pooch_id: int):
    """Get the family of a specific pooch."""
    from src.game import get_pooch_family

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
    from src.game import get_pooch_buy_price

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
    from src.game import get_pooch_sell_price

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
    from src.game import breed_pooches as game_breed_pooches
    from src.game import get_pooch_by_id

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
    from src.game import calculate_incest_level

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
    from src.game import list_server_vendors

    server_id = get_current_server_id()
    vendors = run_async(list_server_vendors(server_id))
    return jsonify([serialize_vendor(v) for v in vendors])


@api_bp.route("/vendors/<int:vendor_id>")
@login_required
def get_vendor(vendor_id: int):
    """Get info about a specific vendor."""
    from src.game import get_vendor_by_id

    try:
        vendor = run_async(get_vendor_by_id(vendor_id))
        return jsonify(serialize_vendor(vendor))
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/vendors/<int:vendor_id>/pooches")
@login_required
def get_vendor_pooches(vendor_id: int):
    """Get all pooches for sale by a vendor."""
    from src.game import get_pooch_buy_price, list_vendor_pooches

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
    from src.game import buy_pooch as game_buy_pooch

    discord_id = get_current_user_id()

    try:
        success, message = run_async(game_buy_pooch(discord_id, vendor_id, pooch_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/vendors/<int:vendor_id>/sell/<int:pooch_id>", methods=["POST"])
@login_required
def sell_pooch_to_vendor(vendor_id: int, pooch_id: int):
    """Sell a pooch to a vendor."""
    from src.game import sell_pooch

    discord_id = get_current_user_id()

    try:
        success, message = run_async(sell_pooch(discord_id, vendor_id, pooch_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/hell")
@login_required
def get_hell_pooches():
    """List all pooches damned to Hell."""
    from src.game import list_hell_pooches

    pooches = run_async(list_hell_pooches())
    return jsonify([serialize_pooch(p) for p in pooches])


@api_bp.route("/hell/summon-price")
@login_required
def get_hell_summon_price():
    """Get the bloodskull cost to summon with the given number of rolls."""
    from src.game import get_summon_pooch_price

    rolls = request.args.get("rolls", 1, type=int)
    price = get_summon_pooch_price(max(rolls, 1))
    return jsonify({"price": price})


@api_bp.route("/hell/summon", methods=["POST"])
@login_required
def summon_hell_pooch():
    """Summon a pooch from Hell."""
    from src.game import summon_pooch

    discord_id = get_current_user_id()
    data = request.json or {}
    num_rolls = max(int(data.get("num_rolls", 1)), 1)

    try:
        success, message = run_async(summon_pooch(discord_id, num_rolls))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/pooches/<int:pooch_id>/bloodskull-value")
@login_required
def get_bloodskull_value(pooch_id: int):
    """Get the bloodskull sacrifice value of a pooch."""
    from src.game import get_pooch_bloodskull_value

    try:
        value = run_async(get_pooch_bloodskull_value(pooch_id))
        return jsonify({"value": value})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>/sacrifice", methods=["POST"])
@login_required
def sacrifice_pooch_route(pooch_id: int):
    """Sacrifice a pooch to Hell for bloodskulls."""
    from src.game import sacrifice_pooch

    discord_id = get_current_user_id()

    try:
        success, message = run_async(sacrifice_pooch(discord_id, pooch_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/graveyard")
@login_required
def get_graveyard():
    """Get all deceased pooches buried by the current user."""
    from src.game import list_graveyard_pooches

    discord_id = get_current_user_id()
    rows = run_async(list_graveyard_pooches(discord_id))
    result = []
    for pooch, buried_at in rows:
        pooch_data = serialize_pooch(pooch)
        pooch_data["buried_at"] = buried_at.isoformat() if buried_at else None
        result.append(pooch_data)
    return jsonify(result)


@api_bp.route("/pooches/<int:pooch_id>/rename", methods=["POST"])
@login_required
def rename_pooch_route(pooch_id: int):
    """Rename a pooch."""
    from src.game import rename_pooch

    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400

    try:
        ok = run_async(rename_pooch(pooch_id, name))
        if ok:
            return jsonify({"success": True})
        return jsonify({"error": "Name is too long"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/kennels/<int:kennel_id>/rename", methods=["POST"])
@login_required
def rename_kennel_route(kennel_id: int):
    """Rename a kennel."""
    from src.game import rename_kennel

    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400

    try:
        ok = run_async(rename_kennel(kennel_id, name))
        if ok:
            return jsonify({"success": True})
        return jsonify({"error": "Name is too long"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/beg", methods=["POST"])
@server_required
def beg_route():
    """Beg for money at the church."""
    from src.game import beg_for_money

    discord_id = get_current_user_id()
    server_id = get_current_server_id()

    try:
        amount, error = run_async(beg_for_money(server_id, discord_id))
        if error:
            return jsonify({"success": False, "amount": 0, "message": error})
        return jsonify({"success": True, "amount": amount, "message": f"You received ${amount}!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/breeds")
@login_required
def get_breeds():
    """Get all breeds."""
    from src.game import list_all_breeds

    breeds = run_async(list_all_breeds())
    return jsonify([serialize_breed(b) for b in breeds])


@api_bp.route("/breeds/<int:breed_id>")
@login_required
def get_breed(breed_id: int):
    """Get a single breed by ID."""
    from src.game import list_all_breeds

    breeds = run_async(list_all_breeds())
    for b in breeds:
        if int(getattr(b, "id", -1)) == int(breed_id):
            return jsonify(serialize_breed(b))
    return jsonify({"error": "Breed not found"}), 404


@api_bp.route("/mutations")
@login_required
def get_mutations():
    """Get all mutations."""
    from src.game import list_all_mutations

    mutations = run_async(list_all_mutations())
    return jsonify([serialize_mutation(m) for m in mutations])


@api_bp.route("/mutations/<int:mutation_id>")
@login_required
def get_mutation(mutation_id: int):
    """Get a single mutation by ID."""
    from src.game import list_all_mutations

    mutations = run_async(list_all_mutations())
    for m in mutations:
        if int(getattr(m, "id", -1)) == int(mutation_id):
            return jsonify(serialize_mutation(m))
    return jsonify({"error": "Mutation not found"}), 404
