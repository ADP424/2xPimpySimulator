from flask import Blueprint, jsonify, request

from src.web.async_utils import run_async
from src.web.auth_utils import (
    get_current_server_id,
    get_current_user_id,
    login_required,
    require_kennel_owner,
    require_pooch_owner,
    require_server_visible_pooch,
    server_required,
)
from src.web.serializers import (
    serialize_bounty_listing,
    serialize_breed,
    serialize_kennel,
    serialize_mutation,
    serialize_owner,
    serialize_pooch,
    serialize_sale_listing,
    serialize_server_event_occurrence,
    serialize_vendor,
)
from src.web.validators import clean_display_name

api_bp = Blueprint("api", __name__)


@api_bp.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


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
    """Get all pooches in a specific kennel. Viewer must own the kennel."""
    from src.game import list_kennel_pooches

    require_kennel_owner(kennel_id)
    try:
        pooches = run_async(list_kennel_pooches(kennel_id))
        return jsonify([serialize_pooch(p) for p in pooches])
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>")
@login_required
def get_pooch(pooch_id: int):
    """Get detailed info about a specific pooch. Requires server-visible ownership."""
    from src.game import get_pooch_by_id

    require_server_visible_pooch(pooch_id)
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

    require_server_visible_pooch(pooch_id)
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


@api_bp.route("/pooches/<int:pooch_id>/family-tree")
@login_required
def get_pooch_family_tree(pooch_id: int):
    """Get the full family tree graph for a pooch."""
    from src.game import get_pooch_family_tree

    require_server_visible_pooch(pooch_id)
    ancestor_depth = request.args.get("ancestor_depth", 5, type=int)
    descendant_depth = request.args.get("descendant_depth", 4, type=int)
    ancestor_depth = min(max(ancestor_depth, 0), 16)
    descendant_depth = min(max(descendant_depth, 0), 16)

    try:
        tree = run_async(get_pooch_family_tree(pooch_id, ancestor_depth, descendant_depth))
        return jsonify(tree)
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
    """Breed two pooches. Viewer must own both."""
    import random

    from src.game import breed_pooches as game_breed_pooches
    from src.game import get_pooch_by_id
    from src.game.breeding import select_actual_mate
    from src.web.validators import coerce_id

    data = request.json or {}
    first_pooch_id = coerce_id(data.get("first_pooch_id"), field="first_pooch_id")
    second_pooch_id = coerce_id(data.get("second_pooch_id"), field="second_pooch_id")

    require_pooch_owner(first_pooch_id)
    require_pooch_owner(second_pooch_id)

    try:
        first_pooch = run_async(get_pooch_by_id(first_pooch_id))
        second_pooch = run_async(get_pooch_by_id(second_pooch_id))

        # Determine male and intended female
        if first_pooch.sex == "male":
            male, intended_female = first_pooch, second_pooch
        else:
            male, intended_female = second_pooch, first_pooch

        # Intelligence-based mate selection (Section 7A)
        rng = random.Random()
        actual_female = run_async(select_actual_mate(male, intended_female, [intended_female], rng=rng))
        distracted = actual_female.id != intended_female.id

        result = run_async(game_breed_pooches(male.id, actual_female.id, return_disease_events=True))
        if isinstance(result, tuple) and len(result) == 2:
            new_pooch_ids, disease_events = result[0], result[1]
        elif isinstance(result, dict):
            new_pooch_ids = result.get("new_pooch_ids", [])
            disease_events = []
        else:
            new_pooch_ids = list(result)
            disease_events = []

        new_pooches = [run_async(get_pooch_by_id(pid)) for pid in new_pooch_ids]
        return jsonify(
            {
                "success": True,
                "new_pooch_ids": new_pooch_ids,
                "new_pooches": [serialize_pooch(p) for p in new_pooches],
                "distracted": distracted,
                "actual_mate_id": actual_female.id,
                "actual_mate_name": actual_female.name,
                "disease_events": disease_events,
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/breeding-chance")
@login_required
def breeding_chance():
    """Return the breeding success chance for a given pooch's intelligence."""
    from src.game.breeding import compute_breeding_chance

    pooch_id = request.args.get("pooch_id", type=int)
    if pooch_id is None:
        return jsonify({"error": "pooch_id required"}), 400
    p = run_async(__import__("src.game", fromlist=["get_pooch_by_id"]).get_pooch_by_id(pooch_id))
    if p is None:
        return jsonify({"error": "Pooch not found"}), 404
    intelligence = int(getattr(p, "intelligence", 10) or 10)
    chance = compute_breeding_chance(intelligence)
    return jsonify({"chance": chance, "chance_pct": round(chance * 100)})


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
    """Buy a pooch from a vendor. The target pooch must currently be vendor-owned."""
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
    """Sell a pooch to a vendor. Viewer must own the pooch."""
    from src.game import sell_pooch

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()

    try:
        success, message = run_async(sell_pooch(discord_id, vendor_id, pooch_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/vendors/<int:vendor_id>/items")
@login_required
def get_vendor_items(vendor_id: int):
    """List items available from a vendor (all catalog items at fixed prices)."""
    from src.database import list_items_by_category

    cleaning = run_async(list_items_by_category("cleaning"))
    food = run_async(list_items_by_category("food"))
    items = cleaning + food
    return jsonify(
        [
            {
                "name": i.name,
                "category": i.category,
                "description": i.description,
                "rarity": i.rarity,
                "price": int((i.parameters or {}).get("price", 10)),
                "parameters": i.parameters,
            }
            for i in items
        ]
    )


@api_bp.route("/vendors/<int:vendor_id>/items/buy", methods=["POST"])
@login_required
def buy_vendor_item(vendor_id: int):
    """
    Buy an item from a vendor. Deducts dollars and adds to owner inventory.
    Body: {"item_name": "Soap", "count": 1}
    """
    from src.database import get_item_by_name, give_owner_item
    from src.game import get_owner_by_discord_id, give_money_to_owner

    data = request.json or {}
    item_name = (data.get("item_name") or "").strip()
    count = max(1, int(data.get("count", 1) or 1))
    if not item_name:
        return jsonify({"error": "item_name required"}), 400

    item = run_async(get_item_by_name(item_name))
    if item is None:
        return jsonify({"error": "Item not found in catalog"}), 404

    unit_price = int((item.parameters or {}).get("price", 10))
    total_cost = unit_price * count

    discord_id = get_current_user_id()
    owner = run_async(get_owner_by_discord_id(discord_id))
    if owner is None or owner.dollars < total_cost:
        return jsonify({"error": f"Not enough money. Cost: ${total_cost}"}), 400

    run_async(give_money_to_owner(discord_id, -total_cost))
    run_async(give_owner_item(discord_id, item_name, count))
    return jsonify({"success": True, "message": f"Purchased {count}x {item_name} for ${total_cost}."})


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
    """Sacrifice a pooch to Hell for bloodskulls. Viewer must own the pooch."""
    from src.game import sacrifice_pooch

    require_pooch_owner(pooch_id)
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
    """Rename a pooch. Viewer must own the pooch."""
    from src.game import rename_pooch
    from src.game.constants import MAX_NAME_LENGTH

    require_pooch_owner(pooch_id)
    data = request.json or {}
    name = clean_display_name(data.get("name"), max_length=MAX_NAME_LENGTH, field="name")

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
    """Rename a kennel. Viewer must own the kennel."""
    from src.game import rename_kennel
    from src.game.constants import MAX_NAME_LENGTH

    require_kennel_owner(kennel_id)
    data = request.json or {}
    name = clean_display_name(data.get("name"), max_length=MAX_NAME_LENGTH, field="name")

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


@api_bp.route("/park/visit", methods=["POST"])
@server_required
def park_visit():
    """Free daily park visit to attract a stray."""
    from src.game import visit_park

    discord_id = get_current_user_id()
    server_id = get_current_server_id()

    try:
        caught, message = run_async(visit_park(server_id, discord_id))
        return jsonify({"success": caught, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/park/bone", methods=["POST"])
@server_required
def park_use_bone():
    """Spend a bone for an extra park attempt."""
    from src.game import spend_bone_at_park

    discord_id = get_current_user_id()
    server_id = get_current_server_id()

    try:
        caught, message = run_async(spend_bone_at_park(server_id, discord_id))
        return jsonify({"success": caught, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/construction/buy-price")
@login_required
def get_kennel_buy_price_route():
    """Get the price to buy the next kennel for the current user."""
    from src.game import get_kennel_buy_price

    discord_id = get_current_user_id()
    price, status = run_async(get_kennel_buy_price(discord_id))
    return jsonify({"price": price, "status": status})


@api_bp.route("/construction/upgrade-price/<int:kennel_id>")
@login_required
def get_kennel_upgrade_price_route(kennel_id: int):
    """Get the price to upgrade a kennel. Verifies the current user owns it."""
    from src.game import get_kennel_upgrade_price

    require_kennel_owner(kennel_id)
    price, status = run_async(get_kennel_upgrade_price(kennel_id))
    return jsonify({"price": price, "status": status})


@api_bp.route("/construction/buy-kennel", methods=["POST"])
@login_required
def buy_kennel_route():
    """Buy a new kennel for the current user."""
    from src.game import buy_kennel

    discord_id = get_current_user_id()

    try:
        success, message = run_async(buy_kennel(discord_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/construction/upgrade-kennel/<int:kennel_id>", methods=["POST"])
@login_required
def upgrade_kennel_route(kennel_id: int):
    """Upgrade a kennel's capacity. Verifies the current user owns it."""
    from src.game import upgrade_kennel

    require_kennel_owner(kennel_id)
    discord_id = get_current_user_id()

    try:
        success, message = run_async(upgrade_kennel(discord_id, kennel_id))
        return jsonify({"success": success, "message": message})
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


# ---------------------------------------------------------------------------
# Section 3 — blood magic rituals
# ---------------------------------------------------------------------------


def _ritual_response(result):
    """Common JSON shape for ritual results."""
    return jsonify(
        {
            "success": result.success,
            "message": result.message,
            "source_pooch_id": result.source_pooch_id,
            "result_pooch_id": result.result_pooch_id,
            "cost_breakdown": result.cost_breakdown,
        }
    )


@api_bp.route("/church/clone/<int:pooch_id>", methods=["POST"])
@login_required
def church_clone(pooch_id: int):
    """Run the clone ritual on a pooch the current user owns."""
    from src.game import clone_pooch_ritual

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    result = run_async(clone_pooch_ritual(discord_id, pooch_id))
    return _ritual_response(result)


@api_bp.route("/church/rejuvenate/<int:pooch_id>", methods=["POST"])
@login_required
def church_rejuvenate(pooch_id: int):
    from src.game import rejuvenate_pooch

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    result = run_async(rejuvenate_pooch(discord_id, pooch_id))
    return _ritual_response(result)


@api_bp.route("/church/gender-change/<int:pooch_id>", methods=["POST"])
@login_required
def church_gender_change(pooch_id: int):
    from src.game import gender_change_pooch

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    result = run_async(gender_change_pooch(discord_id, pooch_id))
    return _ritual_response(result)


@api_bp.route("/church/immortalize/<int:pooch_id>", methods=["POST"])
@login_required
def church_immortalize(pooch_id: int):
    from src.game import immortalize_pooch

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    result = run_async(immortalize_pooch(discord_id, pooch_id))
    return _ritual_response(result)


# ---------------------------------------------------------------------------
# Section 4 / 9 — owner inventory, kennel cleaning, kennel feeding
# ---------------------------------------------------------------------------


@api_bp.route("/owner/items")
@login_required
def get_owner_items():
    """Return the current user's item inventory."""
    from src.database import get_owner_items as db_get_owner_items

    discord_id = get_current_user_id()
    items = run_async(db_get_owner_items(discord_id))
    return jsonify(items)


@api_bp.route("/items")
@login_required
def list_items_route():
    """List the static item catalog."""
    from src.database import list_all_items

    items = run_async(list_all_items())
    return jsonify(
        [
            {
                "name": i.name,
                "alt_name": i.alt_name,
                "category": i.category,
                "description": i.description,
                "rarity": i.rarity,
                "parameters": i.parameters,
            }
            for i in items
        ]
    )


@api_bp.route("/kennels/<int:kennel_id>/clean", methods=["POST"])
@login_required
def kennel_clean_route(kennel_id: int):
    """
    Clean a kennel using either a cleaning item or the free hand-clean.
    Body: {"item_name": "Soap"} or {"item_name": "hand"}
    """
    from src.game import clean_kennel_by_hand, clean_kennel_with_item

    require_kennel_owner(kennel_id)
    discord_id = get_current_user_id()
    data = request.json or {}
    item_name = (data.get("item_name") or "").strip()
    if not item_name:
        return jsonify({"error": "item_name is required"}), 400

    if item_name == "hand":
        ok, msg = run_async(clean_kennel_by_hand(discord_id, kennel_id))
    else:
        ok, msg = run_async(clean_kennel_with_item(discord_id, kennel_id, item_name))
    return jsonify({"success": ok, "message": msg})


@api_bp.route("/kennels/<int:kennel_id>/feed", methods=["POST"])
@login_required
def kennel_feed_route(kennel_id: int):
    """
    Deposit food into a kennel's food stock by consuming a food item from
    inventory. Body: {"item_name": "Kibble", "count": 1}
    """
    from src.database import (
        consume_owner_item,
        get_item_by_name,
        modify_kennel_food_stock,
    )

    require_kennel_owner(kennel_id)
    discord_id = get_current_user_id()
    data = request.json or {}
    item_name = (data.get("item_name") or "").strip()
    if not item_name:
        return jsonify({"error": "item_name is required"}), 400
    count = int(data.get("count", 1) or 1)
    if count < 1:
        return jsonify({"error": "count must be >= 1"}), 400

    item = run_async(get_item_by_name(item_name))
    if item is None or item.category != "food":
        return jsonify({"error": "That item is not food."}), 400

    units = int((item.parameters or {}).get("food_units", 0))
    if units <= 0:
        return jsonify({"error": "Item has no food value."}), 400

    ok = run_async(consume_owner_item(discord_id, item_name, count))
    if not ok:
        return jsonify({"error": f"You don't own {count}x {item_name}."}), 400

    new_stock = run_async(modify_kennel_food_stock(kennel_id, units * count))
    return jsonify({"success": True, "new_stock": new_stock})


# ---------------------------------------------------------------------------
# Section 7D / 8C / 1A — vet procedures (neuter, detailed workup, breed survey)
# ---------------------------------------------------------------------------


@api_bp.route("/vet/neuter/<int:pooch_id>", methods=["POST"])
@login_required
def vet_neuter(pooch_id: int):
    """Neuter a pooch — applies the existing 'Neutered' injury."""
    from src.game import neuter_pooch

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    ok, msg = run_async(neuter_pooch(discord_id, pooch_id))
    return jsonify({"success": ok, "message": msg})


@api_bp.route("/vet/detailed-workup/<int:pooch_id>", methods=["POST"])
@login_required
def vet_detailed_workup(pooch_id: int):
    """Run a Detailed Workup procedure on a pooch."""
    from src.game import detailed_workup

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    ok, msg, report = run_async(detailed_workup(discord_id, pooch_id))
    return jsonify({"success": ok, "message": msg, "report": report})


@api_bp.route("/vet/medical-exam/<int:pooch_id>", methods=["POST"])
@login_required
def vet_medical_exam(pooch_id: int):
    """Run a regular medical exam."""
    from src.game import medical_exam

    require_pooch_owner(pooch_id)
    discord_id = get_current_user_id()
    # Hydrate with the higher-level Pooch model expected by medical_exam.
    from src.game.manage_pooches import get_pooch_by_id as game_get_pooch

    pooch_model = run_async(game_get_pooch(pooch_id))
    ok, msg, report = run_async(medical_exam(discord_id, pooch_model))
    return jsonify({"success": ok, "message": msg, "report": report})


@api_bp.route("/vet/breed-survey")
@server_required
def vet_breed_survey():
    """
    Return the breed population survey for the currently selected server.
    """
    from src.game import breed_population_survey

    server_id = get_current_server_id()
    survey = run_async(breed_population_survey(int(server_id)))
    return jsonify(survey)


# ─────────────────────────────────────────────────────────────────────────────
# Auction house API (Phase 10 web parity)
# ─────────────────────────────────────────────────────────────────────────────


@api_bp.route("/auction/sale-listings")
@server_required
def list_sale_listings():
    """Return all active sale listings for the current server."""
    from src.game.manage_auctions import list_server_sale_listings

    server_id = get_current_server_id()
    listings = run_async(list_server_sale_listings(int(server_id)))
    return jsonify([serialize_sale_listing(listing) for listing in listings])


@api_bp.route("/auction/bounty-listings")
@server_required
def list_bounty_listings():
    """Return all active bounty listings for the current server."""
    from src.game.manage_auctions import list_server_bounty_listings

    server_id = get_current_server_id()
    listings = run_async(list_server_bounty_listings(int(server_id)))
    return jsonify([serialize_bounty_listing(listing) for listing in listings])


@api_bp.route("/auction/my-sale-listings")
@login_required
def list_my_sale_listings():
    """Return all active sale listings created by the current user."""
    from src.game.manage_auctions import list_owner_sale_listings

    discord_id = get_current_user_id()
    listings = run_async(list_owner_sale_listings(int(discord_id)))
    return jsonify([serialize_sale_listing(listing) for listing in listings])


@api_bp.route("/auction/my-bounty-listings")
@login_required
def list_my_bounty_listings():
    """Return all active bounty listings created by the current user."""
    from src.game.manage_auctions import list_owner_bounty_listings

    discord_id = get_current_user_id()
    listings = run_async(list_owner_bounty_listings(int(discord_id)))
    return jsonify([serialize_bounty_listing(listing) for listing in listings])


@api_bp.route("/auction/bid/<int:listing_id>", methods=["POST"])
@login_required
def place_bid_route(listing_id: int):
    """
    Place a bid on a sale listing.
    Body: {"amount": 100}
    """
    from src.game.manage_auctions import place_bid

    discord_id = get_current_user_id()
    data = request.json or {}
    try:
        amount = int(data.get("amount", 0))
    except TypeError, ValueError:
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Bid must be positive"}), 400

    success, message = run_async(place_bid(discord_id, listing_id, amount))
    return jsonify({"success": success, "message": message})


@api_bp.route("/auction/cancel-sale/<int:listing_id>", methods=["POST"])
@login_required
def cancel_sale_listing_route(listing_id: int):
    """Cancel a sale listing the current user owns."""
    from src.game.manage_auctions import close_sale_listing

    discord_id = get_current_user_id()
    success, message = run_async(close_sale_listing(discord_id, listing_id))
    return jsonify({"success": success, "message": message})


@api_bp.route("/auction/cancel-bounty/<int:listing_id>", methods=["POST"])
@login_required
def cancel_bounty_listing_route(listing_id: int):
    """Cancel a bounty listing the current user owns."""
    from src.game.manage_auctions import cancel_bounty_listing

    discord_id = get_current_user_id()
    success, message = run_async(cancel_bounty_listing(discord_id, listing_id))
    return jsonify({"success": success, "message": message})


@api_bp.route("/auction/fulfill-bounty/<int:listing_id>", methods=["POST"])
@login_required
def fulfill_bounty_route(listing_id: int):
    """
    Fulfill a bounty listing with a pooch the current user owns.
    Body: {"pooch_id": 42}
    """
    from src.game.manage_auctions import evaluate_bounty_match, fulfill_bounty

    discord_id = get_current_user_id()
    data = request.json or {}
    try:
        pooch_id = int(data.get("pooch_id", 0))
    except TypeError, ValueError:
        return jsonify({"error": "Invalid pooch_id"}), 400

    require_pooch_owner(pooch_id)
    match = run_async(evaluate_bounty_match(listing_id, pooch_id))
    if not match or match.payout == 0:
        return jsonify({"success": False, "message": "This pooch doesn't match the bounty criteria."}), 400

    success, message = run_async(fulfill_bounty(discord_id, listing_id, pooch_id))
    return jsonify({"success": success, "message": message})


# ─────────────────────────────────────────────────────────────────────────────
# Server events API (Phase 10 web parity)
# ─────────────────────────────────────────────────────────────────────────────


@api_bp.route("/server-events/active")
@server_required
def get_active_server_event():
    """Return the currently active server event for the selected server, or null."""
    from src.database import get_active_server_event_occurrence

    server_id = get_current_server_id()
    occurrence = run_async(get_active_server_event_occurrence(int(server_id)))
    if occurrence is None:
        return jsonify(None)
    return jsonify(serialize_server_event_occurrence(occurrence))


@api_bp.route("/server-events/participate/<int:occurrence_id>", methods=["POST"])
@server_required
def participate_server_event(occurrence_id: int):
    """
    Enter the current user's selected pooch into the active server event.
    Body: {"pooch_id": 42, "menu_option_id": 5}
    """
    from src.game.events.server_events.public import participate_in_server_event

    discord_id = get_current_user_id()
    server_id = get_current_server_id()
    data = request.json or {}
    try:
        pooch_id = int(data.get("pooch_id") or 0) or None
        menu_option_id = int(data.get("menu_option_id", 0))
    except TypeError, ValueError:
        return jsonify({"error": "Invalid parameters"}), 400

    if pooch_id:
        require_pooch_owner(pooch_id)

    success, message, _summary = run_async(
        participate_in_server_event(
            occurrence_id=occurrence_id,
            server_discord_id=int(server_id),
            owner_discord_id=int(discord_id),
            menu_option_id=menu_option_id,
            selected_pooch_id=pooch_id,
        )
    )
    return jsonify({"success": success, "message": message})
