from datetime import datetime
from typing import Any

from src.game import (
    describe_owner_event_result,
    get_disease_treatment_cost,
    get_menu_uses_left,
    get_public_disease_label,
    get_public_injury_label,
    get_treatment_cost,
    get_use_count_per_menu,
    get_used_menu_names,
    is_injury_treated_today,
    menu_is_available,
)


def serialize_datetime(dt: datetime | None) -> str | None:
    """Serialize a datetime to ISO format."""
    if dt is None:
        return None
    return dt.isoformat()


# The only catalog parameters players may see; the rest are hidden stat modifiers.
_PUBLIC_PARAMETER_KEYS = ("sold_by_vendors", "born_from_ritual")


def _public_parameters(entity: Any) -> dict:
    parameters = getattr(entity, "parameters", None) or {}
    return {key: parameters[key] for key in _PUBLIC_PARAMETER_KEYS if key in parameters}


def serialize_breed(breed: Any) -> dict:
    """Serialize a Breed object."""
    return {
        "id": breed.id,
        "name": breed.name,
        "alt_name": breed.alt_name,
        "category": breed.category,
        "description": breed.description,
        "rarity": breed.rarity,
        "parameters": _public_parameters(breed),
    }


def serialize_mutation(mutation: Any) -> dict:
    """Serialize a Mutation object."""
    return {
        "id": mutation.id,
        "name": mutation.name,
        "alt_name": mutation.alt_name,
        "category": mutation.category,
        "description": mutation.description,
        "heritability": mutation.heritability,
        "health_impact": mutation.health_impact,
        "rarity": mutation.rarity,
        "affects_females": mutation.affects_females,
        "affects_males": mutation.affects_males,
        "parameters": _public_parameters(mutation),
    }


def serialize_owner(owner: Any) -> dict:
    """Serialize an Owner object."""
    return {
        "discord_id": owner.discord_id,
        "discord_name": owner.discord_name,
        "dollars": owner.dollars,
        "bloodskulls": owner.bloodskulls,
        "bones": owner.bones,
        "hearts": getattr(owner, "hearts", 0),
        "brains": getattr(owner, "brains", 0),
        "eyes": getattr(owner, "eyes", 0),
        "tails": getattr(owner, "tails", 0),
        "teeth": getattr(owner, "teeth", 0),
        "begged_today": owner.begged_today,
        "visited_park_today": owner.visited_park_today,
    }


def serialize_public_owner(owner: Any) -> dict:
    """Serialize another player as seen by everyone: identity only, never balances."""
    return {
        "discord_id": owner.discord_id,
        "discord_name": owner.discord_name,
    }


def serialize_kennel(kennel: Any) -> dict:
    """Serialize a Kennel object."""
    from src.game.utils.obfuscation import messiness_label

    messiness = getattr(kennel, "messiness", 0) or 0
    pooch_limit = kennel.pooch_limit or 10
    return {
        "id": kennel.id,
        "owner_discord_id": kennel.owner_discord_id,
        "name": kennel.name,
        "pooch_limit": pooch_limit,
        "messiness": messiness,
        "messiness_label": messiness_label(messiness, capacity=pooch_limit),
        "food_stock": getattr(kennel, "food_stock", 0),
    }


def serialize_pooch_breed_info(info: Any) -> dict:
    """Serialize a PoochBreedInfo object."""
    return {
        "breed": serialize_breed(info.breed),
        "relative_weight": info.relative_weight,
    }


def serialize_injury_brief(injury: Any) -> dict:
    """Serialize the public summary of a catalog Injury (as shown on a pooch)."""
    return {
        "id": injury.id,
        "name": injury.name,
        "severity": injury.severity,
        "health_impact": injury.health_impact,
    }


def serialize_disease_brief(disease: Any) -> dict:
    """Serialize the public summary of a catalog Disease (as shown on a pooch)."""
    return {
        "id": disease.id,
        "name": disease.name,
        "category": disease.category,
        "health_impact": disease.health_impact,
    }


def serialize_injury(injury: Any) -> dict:
    """Serialize a catalog Injury for the encyclopedia (the fields the bot's injury info shows)."""
    treated = injury.treated or {}
    return {
        **serialize_injury_brief(injury),
        "description": injury.description,
        "persistence": (injury.parameters or {}).get("persistence"),
        "treated": (
            {"description": treated.get("description") or "Treatable", "health_impact": treated.get("health_impact")}
            if treated
            else None
        ),
    }


def serialize_disease(disease: Any) -> dict:
    """Serialize a catalog Disease for the encyclopedia (the fields the bot's disease info shows)."""
    return {
        **serialize_disease_brief(disease),
        "description": disease.description,
        "contagion_chance": disease.contagion_chance,
        "sexually_transmitted": disease.sexually_transmitted,
        "recovery_chance": disease.recovery_chance,
        "treatable": disease.treatable,
        "curable": disease.curable,
        "heritability": disease.heritability,
        "seasons": disease.seasons or [],
        "immunity_duration": disease.immunity_duration,
    }


def serialize_owner_event_outcome(result: Any, entity_references: Any) -> dict | None:
    """The described outcome of an owner event; never the raw result (it holds the outcome chance)."""
    if result is None:
        return None
    description = describe_owner_event_result(result, entity_references)
    return {"headline": description.headline, "lines": description.lines}


def serialize_owner_event_references(context: Any, entity_references: Any) -> dict:
    """Pooches, breeds and mutations an event involves (as the bot's Related field), plus kennel labels."""
    kennel_ids: list[int] = []
    for kennel_id in [context.selected_kennel_id, *context.affected_kennel_ids]:
        if kennel_id is not None and kennel_id not in kennel_ids:
            kennel_ids.append(kennel_id)
    references = {
        kind: [{"id": ref.id, "label": ref.label} for ref in entity_references.for_kind(kind)]
        for kind in ("pooches", "breeds", "mutations")
    }
    references["kennels"] = [f"Kennel #{kennel_id}" for kennel_id in kennel_ids]
    return references


def _featured_pooch(event: Any) -> dict | None:
    pooch_id = event.featured_pooch_id
    if pooch_id is None:
        return None
    label = next((ref.label for ref in event.entity_references.pooches if ref.id == pooch_id), f"Pooch #{pooch_id}")
    return {"id": pooch_id, "label": label}


def serialize_triggered_owner_event(event: Any) -> dict:
    """A pending or just-triggered owner event (options are already filtered to the visible ones)."""
    return {
        "id": event.active_owner_event_id,
        "name": event.name,
        "description": event.description,
        "flavor_text": event.flavor_text,
        "category": event.category,
        "severity": event.severity,
        "requires_response": event.requires_response,
        "expires_at": serialize_datetime(event.expires_at),
        "featured_pooch": _featured_pooch(event),
        "references": serialize_owner_event_references(event.context, event.entity_references),
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "description": option.description,
                "min_money": option.min_money,
                "min_bloodskulls": option.min_bloodskulls,
            }
            for option in (event.options if event.requires_response else [])
        ],
        "outcome": serialize_owner_event_outcome(event.result, event.entity_references),
    }


def serialize_owner_event_history(record: Any) -> dict:
    """A finished owner event from the owner's history."""
    if record.timed_out:
        status = "timed_out"
    elif record.selected_option_label:
        status = "responded"
    else:
        status = "auto_resolved"
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "flavor_text": record.flavor_text,
        "category": record.category,
        "severity": record.severity,
        "triggered_at": serialize_datetime(record.triggered_at),
        "completed_at": serialize_datetime(record.completed_at),
        "status": status,
        "selected_option_label": record.selected_option_label,
        "references": serialize_owner_event_references(record.context, record.entity_references),
        "outcome": serialize_owner_event_outcome(record.result_summary, record.entity_references),
    }


def _serialize_viewer_participation(participation: Any) -> dict:
    """The viewer's own server-event entries, as the bot's "Your status" field shows them."""
    if participation is None:
        return {"participated": False, "submissions": [], "rank": None, "resolution_message": None}

    def _pooch_label(pooch_id: Any) -> str:
        return next(
            (ref.label for ref in participation.entity_references.pooches if ref.id == pooch_id), f"Pooch #{pooch_id}"
        )

    submissions = []
    for sub in participation.submissions or []:
        immediate = sub.get("immediate_result") or {}
        pooch_id = sub.get("selected_pooch_id")
        submissions.append(
            {
                "menu_name": sub.get("menu_name", "?"),
                "option_label": sub.get("option_label", "?"),
                "pooch_label": _pooch_label(pooch_id) if pooch_id is not None else None,
                "message": immediate.get("message") if isinstance(immediate, dict) else None,
            }
        )
    resolution = participation.resolution_result
    return {
        "participated": True,
        "submissions": submissions,
        "rank": participation.rank,
        "resolution_message": resolution.message if resolution is not None and resolution.message else None,
    }


def serialize_server_event(event: Any) -> dict:
    """
    The active server event as a participant sees it.

    Menu availability and uses left come from the game rules; options only say whether they need a pooch,
    never their filters, scoring or parameters.
    """
    submissions = event.viewer_participation.submissions if event.viewer_participation is not None else None
    used_names = get_used_menu_names(submissions)
    use_counts = get_use_count_per_menu(submissions)
    return {
        "occurrence_id": event.occurrence_id,
        "name": event.name,
        "description": event.description,
        "flavor_text": event.flavor_text,
        "category": event.category,
        "severity": event.severity,
        "expires_at": serialize_datetime(event.expires_at),
        "participation_count": event.participation_count,
        "menus": [
            {
                "id": menu.id,
                "name": menu.name,
                "label": menu.label,
                "description": menu.description,
                "depends_on": list(menu.depends_on),
                "available": menu_is_available(menu, used_names, use_counts),
                "uses_left": get_menu_uses_left(menu, use_counts),
                "options": [
                    {
                        "id": option.id,
                        "label": option.label,
                        "description": option.description,
                        "requires_pooch": bool(option.requires.get("pooch")),
                    }
                    for option in menu.options
                ],
            }
            for menu in event.menus
        ],
        "viewer": _serialize_viewer_participation(event.viewer_participation),
    }


def serialize_timeline_entry(entry: Any) -> dict:
    """Serialize a PoochTimelineEntry."""
    return {
        "kind": entry.kind,
        "description": entry.description,
        "snapshot_at": serialize_datetime(entry.snapshot_at),
        "entity_names": entry.entity_names,
    }


def serialize_patient_summary(pooch: Any) -> dict:
    """A pooch as listed in its owner's Patient Room (counts only, as the bot shows)."""
    return {
        "id": pooch.id,
        "name": pooch.name,
        "vet_checked": pooch.vet_checked,
        "injury_count": len(pooch.injuries),
        "undiagnosed_mutation_count": sum(1 for pm in pooch.mutations if not pm.visible),
    }


def serialize_patient_injury(pooch_injury: Any) -> dict:
    """One of the owner's pooch's injuries in the Patient Room; hidden ones show their symptom, not their name."""
    return {
        "id": pooch_injury.id,
        "label": get_public_injury_label(pooch_injury),
        "visible": pooch_injury.visible,
        "injury_id": pooch_injury.injury_id if pooch_injury.visible else None,
        "severity": pooch_injury.injury.severity,
        "persistence": pooch_injury.persistence,
        "cost": get_treatment_cost(pooch_injury.injury.severity),
        "treated": pooch_injury.treated,
        "treated_today": is_injury_treated_today(pooch_injury),
    }


def serialize_patient_disease(pooch_disease: Any) -> dict:
    """One of the owner's pooch's diseases in the Patient Room; hidden ones show their symptom, not their name."""
    return {
        "id": pooch_disease.id,
        "label": get_public_disease_label(pooch_disease),
        "visible": pooch_disease.visible,
        "disease_id": pooch_disease.disease_id if pooch_disease.visible else None,
        "treated": pooch_disease.treated,
        "treatable": pooch_disease.disease.treatable,
        "curable": pooch_disease.disease.curable,
        "cost": get_disease_treatment_cost(),
    }


def _hidden_symptoms(instances: list) -> list[str]:
    """Symptoms of hidden conditions; never their names or ids."""
    return [inst.displayed_symptom for inst in instances if not inst.visible and inst.displayed_symptom]


def serialize_pooch(pooch: Any, include_relations: bool = True) -> dict:
    """
    Serialize a Pooch object as any player may see it.

    Exact health, hunger and breeding cooldown stay hidden (only their labels are sent), and hidden
    mutations, injuries and diseases appear only as their displayed symptoms.
    """
    from src.game.utils.obfuscation import health_label, starvation_label

    data = {
        "id": pooch.id,
        "name": pooch.name,
        "age": pooch.age,
        "sex": pooch.sex,
        "alive": pooch.alive,
        "virgin": pooch.virgin,
        "owner_discord_id": pooch.owner_discord_id,
        "vendor_id": pooch.vendor_id,
        "created_at": serialize_datetime(pooch.created_at),
        "birthday": serialize_datetime(pooch.birthday),
        "health_label": health_label(pooch.health),
        "status": pooch.status,
        "breeding_status": pooch.breeding_status,
        "can_breed": pooch.can_breed,
        "mood": pooch.mood,
        "pregnant": getattr(pooch, "pregnancy_timer", None) is not None,
        "immortal": getattr(pooch, "immortal", False),
        "rejuvenation_count": getattr(pooch, "rejuvenation_count", 0),
        "starvation_label": starvation_label(getattr(pooch, "starvation", 0) or 0),
    }

    if include_relations:
        data["breeds"] = [serialize_pooch_breed_info(b) for b in pooch.breeds]
        data["mutations"] = [serialize_mutation(pm.mutation) for pm in pooch.mutations if pm.visible]
        data["injuries"] = [serialize_injury_brief(pi.injury) for pi in pooch.injuries if pi.visible]
        data["diseases"] = [
            {**serialize_disease_brief(pd.disease), "treated": pd.treated} for pd in pooch.diseases if pd.visible
        ]
        data["mutation_symptoms"] = _hidden_symptoms(pooch.mutations)
        data["injury_symptoms"] = _hidden_symptoms(pooch.injuries)
        data["disease_symptoms"] = _hidden_symptoms(pooch.diseases)
        if pooch.owner is not None:
            data["owner"] = serialize_public_owner(pooch.owner)
        if pooch.vendor is not None:
            data["vendor"] = {"id": pooch.vendor.id, "name": pooch.vendor.name}

    return data


def serialize_vendor(vendor: Any) -> dict:
    """Serialize a Vendor object."""
    data = {
        "id": vendor.id,
        "server_discord_id": vendor.server_discord_id,
        "name": vendor.name,
        "stock_count": vendor.stock_count,
        "desired_mutations": [],
        "desired_breeds": [],
    }

    for mutation in vendor.desired_mutations:
        data["desired_mutations"].append(serialize_mutation(mutation))

    for breed in vendor.desired_breeds:
        data["desired_breeds"].append(serialize_breed(breed))

    return data


def serialize_birth_event(event: Any) -> dict:
    """Serialize a BirthEvent object."""
    return {
        "type": "birth",
        "mother": serialize_pooch(event.mother, include_relations=False),
        "child": serialize_pooch(event.child, include_relations=False),
        "message": event.message,
    }


def serialize_death_event(event: Any) -> dict:
    """Serialize a DeathEvent object."""
    return {
        "type": "death",
        "pooch": serialize_pooch(event.pooch, include_relations=False),
        "message": event.message,
    }


def serialize_other_event(event: Any) -> dict:
    """Serialize an OtherEvent object."""
    return {
        "type": "other",
        "pooch": serialize_pooch(event.pooch, include_relations=False),
        "message": event.message,
    }


def serialize_auction_sale_listing(listing: Any) -> dict:
    """Serialize a game-layer AuctionSaleListing."""
    return {
        "id": listing.id,
        "pooch": serialize_pooch(listing.pooch) if listing.pooch else None,
        "seller_discord_id": listing.seller_discord_id,
        "server_discord_id": listing.server_discord_id,
        "minimum_bid": listing.minimum_bid,
        "created_at": serialize_datetime(listing.created_at),
        "expires_at": serialize_datetime(listing.expires_at),
        "is_active": listing.is_active,
        "highest_bid": listing.highest_bid,
        "highest_bidder_discord_id": listing.highest_bidder_discord_id,
        "bid_count": listing.bid_count,
    }


def serialize_auction_bounty_listing(listing: Any) -> dict:
    """Serialize a game-layer AuctionBountyListing."""
    return {
        "id": listing.id,
        "buyer_discord_id": listing.buyer_discord_id,
        "server_discord_id": listing.server_discord_id,
        "title": listing.title,
        "escrow_amount": listing.escrow_amount,
        "criteria": listing.criteria,
        "created_at": serialize_datetime(listing.created_at),
        "is_active": listing.is_active,
    }


def serialize_bounty_match_result(result: Any) -> dict:
    """Serialize a BountyMatchResult."""
    return {
        "listing_id": result.listing_id,
        "matched_criteria": result.matched_criteria,
        "payout": result.payout,
    }


def serialize_item(item: Any) -> dict:
    """Serialize a catalog Item."""
    return {
        "name": item.name,
        "alt_name": item.alt_name,
        "category": item.category,
        "description": item.description,
        "rarity": item.rarity,
        "parameters": item.parameters,
    }


def serialize_day_change_summary(summary: Any) -> dict:
    """Serialize a DayChangeSummary object."""
    return {
        "server_discord_id": summary.server.discord_id,
        "births": [serialize_birth_event(e) for e in summary.births],
        "deaths": [serialize_death_event(e) for e in summary.deaths],
        "other_events": [serialize_other_event(e) for e in summary.other_events],
    }
