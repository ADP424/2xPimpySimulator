from flask import Blueprint, jsonify, request

from src.web.async_utils import run_async
from src.web.auth_utils import (
    get_current_server_id,
    get_current_user_id,
    login_required,
    server_required,
)
from src.web.serializers import (
    serialize_auction_bounty_listing,
    serialize_auction_sale_listing,
    serialize_bounty_match_result,
    serialize_breed,
    serialize_disease,
    serialize_injury,
    serialize_kennel,
    serialize_mutation,
    serialize_owner,
    serialize_owner_event_history,
    serialize_owner_event_outcome,
    serialize_owner_event_references,
    serialize_patient_disease,
    serialize_patient_injury,
    serialize_patient_summary,
    serialize_pooch,
    serialize_server_event,
    serialize_timeline_entry,
    serialize_triggered_owner_event,
    serialize_vendor,
)

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
        # Compared here because JS numbers can't hold 64-bit Discord IDs exactly
        return jsonify({**serialize_pooch(pooch), "viewer_is_owner": pooch.owner_discord_id == get_current_user_id()})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/pooches/<int:pooch_id>/timeline")
@login_required
def get_pooch_timeline(pooch_id: int):
    """Get a pooch's timeline, oldest first."""
    from src.game import get_pooch_timeline

    entries = run_async(get_pooch_timeline(pooch_id))
    return jsonify([serialize_timeline_entry(entry) for entry in entries])


@api_bp.route("/pooches/<int:pooch_id>/cast-out", methods=["POST"])
@server_required
def cast_out_pooch_route(pooch_id: int):
    """Cast one of the current user's pooches out to the server's strays."""
    from src.game import cast_out_pooch

    success, message = run_async(cast_out_pooch(get_current_user_id(), pooch_id, get_current_server_id()))
    return jsonify({"success": success, "message": message})


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


@api_bp.route("/pooches/<int:pooch_id>/family-tree")
@login_required
def get_pooch_family_tree(pooch_id: int):
    """Get the full family tree graph for a pooch."""
    from src.game import get_pooch_family_tree

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
    """Breed two pooches."""
    from src.game import breed_pooches as game_breed_pooches
    from src.game import get_pooch_by_id

    data = request.json
    first_pooch_id = data.get("first_pooch_id")
    second_pooch_id = data.get("second_pooch_id")

    if not first_pooch_id or not second_pooch_id:
        return jsonify({"error": "Both pooch IDs are required"}), 400

    try:
        # The puppies are fetuses until the next day change, so only their count is reported
        puppy_ids, disease_events = run_async(
            game_breed_pooches(first_pooch_id, second_pooch_id, return_disease_events=True)
        )
        first = run_async(get_pooch_by_id(first_pooch_id))
        second = run_async(get_pooch_by_id(second_pooch_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 404

    # Same wording as the bot's breeding reply
    puppy_count = len(puppy_ids)
    if puppy_count == 1:
        message = f"**Breeding successful.** {first.name} and {second.name} are expecting **1** puppy."
    elif puppy_count == 2:
        message = f"**Twins!** {first.name} and {second.name} are expecting **2** puppies."
    else:
        message = f"**Triplets!** {first.name} and {second.name} are expecting **{puppy_count}** puppies."

    disease_lines = []
    for pooch_id, public_label, event_type in disease_events:
        if event_type == "spread":
            name = first.name if pooch_id == first.id else second.name if pooch_id == second.id else "A puppy"
            disease_lines.append(f"{name} was exposed to {public_label}.")
        elif event_type == "inherited":
            disease_lines.append(f"A puppy inherited {public_label}.")

    return jsonify({"success": True, "puppy_count": puppy_count, "message": message, "disease_lines": disease_lines})


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


@api_bp.route("/kennels/<int:kennel_id>/clean", methods=["POST"])
@server_required
def clean_kennel_route(kennel_id: int):
    """Clean one of the current user's kennels, resetting its messiness."""
    from src.game import clean_kennel

    success, message = run_async(clean_kennel(get_current_user_id(), kennel_id))
    return jsonify({"success": success, "message": message})


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
    from src.game import get_kennel_upgrade_price, list_owner_kennels

    discord_id = get_current_user_id()
    kennels = run_async(list_owner_kennels(discord_id))
    if not any(k.id == kennel_id for k in kennels):
        return jsonify({"error": "You don't own that kennel"}), 403

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
    from src.game import list_owner_kennels, upgrade_kennel

    discord_id = get_current_user_id()

    kennels = run_async(list_owner_kennels(discord_id))
    if not any(k.id == kennel_id for k in kennels):
        return jsonify({"error": "You don't own that kennel"}), 403

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
# Owner events
# ---------------------------------------------------------------------------

# respond_to_event failures after which the event can no longer be answered (as the bot treats them)
_TERMINAL_EVENT_MESSAGES = {
    "This event has expired.",
    "You have already responded to this event.",
    "Event not found.",
}


@api_bp.route("/events/pending")
@server_required
def get_pending_events():
    """The current user's owner events still waiting for a response."""
    from src.game import get_active_events_for_owner

    events = run_async(get_active_events_for_owner(get_current_user_id(), pending_only=True))
    return jsonify([serialize_triggered_owner_event(event) for event in events])


@api_bp.route("/events/history")
@server_required
def get_events_history():
    """The current user's finished owner events, newest first."""
    from src.game import get_event_history

    limit = min(max(request.args.get("limit", 25, type=int), 1), 50)
    records = run_async(get_event_history(get_current_user_id(), limit=limit))
    return jsonify([serialize_owner_event_history(record) for record in records])


@api_bp.route("/events/<int:active_owner_event_id>/respond", methods=["POST"])
@server_required
def respond_to_event_route(active_owner_event_id: int):
    """Respond to one of the current user's pending owner events."""
    from src.game import get_pending_event, respond_to_event
    from src.game.models.events import resolve_owner_event_entity_references

    option_id = (request.json or {}).get("option_id")
    if not isinstance(option_id, int):
        return jsonify({"error": "option_id is required"}), 400

    discord_id = get_current_user_id()
    event = run_async(get_pending_event(discord_id, active_owner_event_id))
    if event is None:
        return jsonify({"success": False, "message": "Event not found.", "closed": True, "outcome": None})

    success, message, result = run_async(respond_to_event(discord_id, active_owner_event_id, option_id))
    references = event.entity_references
    if result is not None:
        references = run_async(
            resolve_owner_event_entity_references(event.context, result, existing=event.entity_references)
        )
    option = next((option for option in event.options if option.id == option_id), None)
    return jsonify(
        {
            "success": success,
            "message": message,
            "closed": success or message in _TERMINAL_EVENT_MESSAGES,
            "selected_option_label": option.label if success and option is not None else None,
            "outcome": serialize_owner_event_outcome(result, references),
            "references": serialize_owner_event_references(event.context, references),
        }
    )


# ---------------------------------------------------------------------------
# Server events
# ---------------------------------------------------------------------------


@api_bp.route("/server-event")
@server_required
def get_server_event():
    """The current server's active server event, with the viewer's own participation."""
    from src.game import get_active_server_event

    event = run_async(get_active_server_event(get_current_server_id(), viewer_owner_discord_id=get_current_user_id()))
    return jsonify({"event": serialize_server_event(event) if event is not None else None})


@api_bp.route("/server-event/<int:occurrence_id>/participate", methods=["POST"])
@server_required
def participate_in_server_event_route(occurrence_id: int):
    """Enter the active server event with one of its menu options (and a pooch, if the option needs one)."""
    from src.game import participate_in_server_event

    data = request.json or {}
    option_id = data.get("option_id")
    pooch_id = data.get("pooch_id")
    if not isinstance(option_id, int):
        return jsonify({"error": "option_id is required"}), 400
    if pooch_id is not None and not isinstance(pooch_id, int):
        return jsonify({"error": "pooch_id must be an integer"}), 400

    success, message, _summary = run_async(
        participate_in_server_event(
            occurrence_id,
            get_current_server_id(),
            get_current_user_id(),
            option_id,
            selected_pooch_id=pooch_id,
        )
    )
    return jsonify({"success": success, "message": message})


# ---------------------------------------------------------------------------
# Veterinary clinic — Patient Room
# ---------------------------------------------------------------------------


def _load_own_pooch(pooch_id: int):
    """Return (pooch, None) if the current user owns the pooch, else (None, error response)."""
    from src.game import get_pooch_by_id

    try:
        pooch = run_async(get_pooch_by_id(pooch_id))
    except Exception:
        return None, (jsonify({"error": "Pooch not found"}), 404)
    if pooch.owner_discord_id != get_current_user_id():
        return None, (jsonify({"error": "That's not your pooch."}), 403)
    return pooch, None


@api_bp.route("/clinic/patients")
@server_required
def get_clinic_patients():
    """The current user's pooches grouped by kennel, as listed in the Patient Room."""
    from src.game import list_kennel_pooches, list_owner_kennels

    discord_id = get_current_user_id()
    result = []
    for kennel in run_async(list_owner_kennels(discord_id)):
        pooches = run_async(list_kennel_pooches(kennel.id))
        if not pooches:
            continue
        result.append(
            {
                "kennel": {"id": kennel.id, "name": kennel.name},
                "pooches": [serialize_patient_summary(p) for p in pooches],
            }
        )
    return jsonify(result)


@api_bp.route("/pooches/<int:pooch_id>/patient")
@server_required
def get_patient(pooch_id: int):
    """Patient Room details for one of the current user's pooches."""
    from src.game import (
        MEDICAL_EXAM_COST,
        get_diagnose_diseases_cost,
        get_diagnose_injuries_cost,
        get_diagnose_mutations_cost,
        get_pooch_disease_instances,
        get_pooch_injury_instances,
    )

    pooch, error = _load_own_pooch(pooch_id)
    if error:
        return error

    injuries = run_async(get_pooch_injury_instances(pooch_id))
    diseases = run_async(get_pooch_disease_instances(pooch_id))
    return jsonify(
        {
            **serialize_patient_summary(pooch),
            "disease_count": len(pooch.diseases),
            "undiagnosed_disease_count": sum(1 for pd in pooch.diseases if not pd.visible),
            "injuries": [serialize_patient_injury(pi) for pi in injuries],
            "diseases": [serialize_patient_disease(pd) for pd in diseases],
            "costs": {
                "diagnose_injuries": get_diagnose_injuries_cost(),
                "diagnose_mutations": get_diagnose_mutations_cost(),
                "diagnose_diseases": get_diagnose_diseases_cost(),
                "medical_exam": MEDICAL_EXAM_COST,
            },
        }
    )


@api_bp.route("/clinic/injuries/<int:pooch_injury_id>/treat", methods=["POST"])
@server_required
def treat_injury_route(pooch_injury_id: int):
    """Treat one of the current user's pooch's injuries."""
    from src.game import treat_injury

    success, message, cost = run_async(treat_injury(get_current_user_id(), pooch_injury_id))
    return jsonify({"success": success, "message": message, "cost": cost})


@api_bp.route("/clinic/diseases/<int:pooch_disease_id>/treat", methods=["POST"])
@server_required
def treat_disease_route(pooch_disease_id: int):
    """Treat one of the current user's pooch's diseases."""
    from src.game import treat_disease

    success, message, cost = run_async(treat_disease(get_current_user_id(), pooch_disease_id))
    return jsonify({"success": success, "message": message, "cost": cost})


@api_bp.route("/pooches/<int:pooch_id>/diagnose/<kind>", methods=["POST"])
@server_required
def diagnose_route(pooch_id: int, kind: str):
    """Diagnose a pooch's hidden injuries, mutations or diseases."""
    from src.game import diagnose_diseases, diagnose_injuries, diagnose_mutations

    diagnose_by_kind = {
        "injuries": (diagnose_injuries, "injuries"),
        "mutations": (diagnose_mutations, "mutations"),
        "diseases": (diagnose_diseases, "diseases"),
    }
    if kind not in diagnose_by_kind:
        return jsonify({"error": "Unknown diagnosis"}), 404

    pooch, error = _load_own_pooch(pooch_id)
    if error:
        return error
    diagnose, attribute = diagnose_by_kind[kind]
    hidden_before = sum(1 for instance in getattr(pooch, attribute) if not instance.visible)

    success, message, revealed = run_async(diagnose(get_current_user_id(), pooch_id))
    return jsonify(
        {
            "success": success,
            "message": message,
            "revealed": revealed,
            "fully_diagnosed": success and len(revealed) >= hidden_before,
        }
    )


@api_bp.route("/pooches/<int:pooch_id>/medical-exam", methods=["POST"])
@server_required
def medical_exam_route(pooch_id: int):
    """Run a medical exam on one of the current user's pooches."""
    from src.game import medical_exam

    pooch, error = _load_own_pooch(pooch_id)
    if error:
        return error

    success, message, report = run_async(medical_exam(get_current_user_id(), pooch))
    # A list of pairs keeps the bot's stat order (jsonify sorts dict keys)
    return jsonify({"success": success, "message": message, "report": list(report.items())})


@api_bp.route("/injuries")
@login_required
def get_injuries():
    """Get all injuries."""
    from src.game import list_all_injuries

    injuries = run_async(list_all_injuries())
    return jsonify([serialize_injury(i) for i in injuries])


@api_bp.route("/injuries/<int:injury_id>")
@login_required
def get_injury(injury_id: int):
    """Get a single injury by ID."""
    from src.game import get_injury_by_id

    injury = run_async(get_injury_by_id(injury_id))
    if injury is None:
        return jsonify({"error": "Injury not found"}), 404
    return jsonify(serialize_injury(injury))


@api_bp.route("/diseases")
@login_required
def get_diseases():
    """Get all diseases."""
    from src.game import list_all_diseases

    diseases = run_async(list_all_diseases())
    return jsonify([serialize_disease(d) for d in diseases])


@api_bp.route("/diseases/<int:disease_id>")
@login_required
def get_disease(disease_id: int):
    """Get a single disease by ID."""
    from src.game import get_disease_by_id

    disease = run_async(get_disease_by_id(disease_id))
    if disease is None:
        return jsonify({"error": "Disease not found"}), 404
    return jsonify(serialize_disease(disease))


# ---------------------------------------------------------------------------
# Auction — Sale Listings
# ---------------------------------------------------------------------------


@api_bp.route("/auctions/sales")
@server_required
def get_server_sale_listings():
    """List all active sale listings for the current server."""
    from src.game import list_server_sale_listings

    server_id = get_current_server_id()
    listings = run_async(list_server_sale_listings(server_id))
    return jsonify([serialize_auction_sale_listing(l) for l in listings])


@api_bp.route("/auctions/sales/mine")
@server_required
def get_my_sale_listings():
    """List the current user's active sale listings."""
    from src.game import list_owner_sale_listings

    discord_id = get_current_user_id()
    listings = run_async(list_owner_sale_listings(discord_id))
    return jsonify([serialize_auction_sale_listing(l) for l in listings])


@api_bp.route("/auctions/sales/<int:listing_id>")
@server_required
def get_sale_listing_detail(listing_id: int):
    """Get a single sale listing."""
    from src.game import get_sale_listing

    listing = run_async(get_sale_listing(listing_id))
    if listing is None:
        return jsonify({"error": "Listing not found"}), 404
    return jsonify(serialize_auction_sale_listing(listing))


@api_bp.route("/auctions/sales", methods=["POST"])
@server_required
def create_sale_listing_route():
    """Create a new sale listing."""
    from src.game import create_sale_listing

    discord_id = get_current_user_id()
    server_id = get_current_server_id()
    data = request.json or {}
    pooch_id = data.get("pooch_id")
    minimum_bid = data.get("minimum_bid", 0)
    duration_hours = data.get("duration_hours")

    if not pooch_id:
        return jsonify({"error": "pooch_id is required"}), 400
    if not isinstance(minimum_bid, int) or minimum_bid < 0:
        return jsonify({"error": "minimum_bid must be a non-negative integer"}), 400

    try:
        success, message = run_async(
            create_sale_listing(discord_id, pooch_id, server_id, minimum_bid, duration_hours)
        )
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/auctions/sales/<int:listing_id>/bid", methods=["POST"])
@server_required
def place_bid_route(listing_id: int):
    """Place a bid on a sale listing."""
    from src.game import place_bid

    discord_id = get_current_user_id()
    data = request.json or {}
    amount = data.get("amount")

    if not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "amount must be a positive integer"}), 400

    try:
        success, message = run_async(place_bid(discord_id, listing_id, amount))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/auctions/sales/<int:listing_id>/close", methods=["POST"])
@server_required
def close_sale_listing_route(listing_id: int):
    """Close a sale listing (owner only)."""
    from src.game import close_sale_listing

    discord_id = get_current_user_id()

    try:
        success, message = run_async(close_sale_listing(discord_id, listing_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Auction — Bounty Listings
# ---------------------------------------------------------------------------


@api_bp.route("/auctions/bounties")
@server_required
def get_server_bounty_listings():
    """List all active bounty listings for the current server."""
    from src.game import list_server_bounty_listings

    server_id = get_current_server_id()
    listings = run_async(list_server_bounty_listings(server_id))
    return jsonify([serialize_auction_bounty_listing(l) for l in listings])


@api_bp.route("/auctions/bounties/mine")
@server_required
def get_my_bounty_listings():
    """List the current user's active bounty listings."""
    from src.game import list_owner_bounty_listings

    discord_id = get_current_user_id()
    listings = run_async(list_owner_bounty_listings(discord_id))
    return jsonify([serialize_auction_bounty_listing(l) for l in listings])


@api_bp.route("/auctions/bounties", methods=["POST"])
@server_required
def create_bounty_listing_route():
    """Create a new bounty listing."""
    from src.game import create_bounty_listing

    discord_id = get_current_user_id()
    server_id = get_current_server_id()
    data = request.json or {}
    title = data.get("title", "Wanted")
    escrow_amount = data.get("escrow_amount")
    criteria = data.get("criteria", [])

    if not isinstance(escrow_amount, int) or escrow_amount <= 0:
        return jsonify({"error": "escrow_amount must be a positive integer"}), 400
    if not criteria:
        return jsonify({"error": "At least one criterion is required"}), 400

    try:
        success, message = run_async(
            create_bounty_listing(discord_id, server_id, title, escrow_amount, criteria)
        )
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/auctions/bounties/<int:listing_id>/match/<int:pooch_id>")
@server_required
def evaluate_bounty_match_route(listing_id: int, pooch_id: int):
    """Evaluate how well a pooch matches a bounty's criteria."""
    from src.game import evaluate_bounty_match

    try:
        result = run_async(evaluate_bounty_match(listing_id, pooch_id))
        return jsonify(serialize_bounty_match_result(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/auctions/bounties/<int:listing_id>/fulfill", methods=["POST"])
@server_required
def fulfill_bounty_route(listing_id: int):
    """Fulfill a bounty listing by selling a pooch."""
    from src.game import fulfill_bounty

    discord_id = get_current_user_id()
    data = request.json or {}
    pooch_id = data.get("pooch_id")

    if not pooch_id:
        return jsonify({"error": "pooch_id is required"}), 400

    try:
        success, message = run_async(fulfill_bounty(discord_id, listing_id, pooch_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/auctions/bounties/<int:listing_id>/cancel", methods=["POST"])
@server_required
def cancel_bounty_listing_route(listing_id: int):
    """Cancel a bounty listing (owner only)."""
    from src.game import cancel_bounty_listing

    discord_id = get_current_user_id()

    try:
        success, message = run_async(cancel_bounty_listing(discord_id, listing_id))
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
