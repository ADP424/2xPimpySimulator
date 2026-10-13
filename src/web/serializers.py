from datetime import datetime
from typing import Any


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
    return {
        "id": kennel.id,
        "owner_discord_id": kennel.owner_discord_id,
        "name": kennel.name,
        "pooch_limit": kennel.pooch_limit,
        "messiness": kennel.messiness,
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


def _hidden_symptoms(instances: list) -> list[str]:
    """Symptoms of hidden conditions; never their names or ids."""
    return [inst.displayed_symptom for inst in instances if not inst.visible and inst.displayed_symptom]


def serialize_pooch(pooch: Any, include_relations: bool = True) -> dict:
    """
    Serialize a Pooch object as any player may see it.

    Exact health and breeding cooldown stay hidden (the bot shows only status labels), and hidden
    mutations, injuries and diseases appear only as their displayed symptoms.
    """
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
        "status": pooch.status,
        "breeding_status": pooch.breeding_status,
        "can_breed": pooch.can_breed,
        "mood": pooch.mood,
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
        "price_markup": vendor.price_markup,
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
        "pooch": serialize_pooch(listing.pooch),
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


def serialize_day_change_summary(summary: Any) -> dict:
    """Serialize a DayChangeSummary object."""
    return {
        "server_discord_id": summary.server.discord_id,
        "births": [serialize_birth_event(e) for e in summary.births],
        "deaths": [serialize_death_event(e) for e in summary.deaths],
        "other_events": [serialize_other_event(e) for e in summary.other_events],
    }
