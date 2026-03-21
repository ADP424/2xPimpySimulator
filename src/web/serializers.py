from datetime import datetime
from typing import Any


def serialize_datetime(dt: datetime | None) -> str | None:
    """Serialize a datetime to ISO format."""
    if dt is None:
        return None
    return dt.isoformat()


def serialize_breed(breed: Any) -> dict:
    """Serialize a Breed object."""
    return {
        "id": breed.id,
        "name": breed.name,
        "alt_name": breed.alt_name,
        "category": breed.category,
        "description": breed.description,
        "rarity": breed.rarity,
        "parameters": getattr(breed, "parameters", {}),
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
        "parameters": getattr(mutation, "parameters", {}),
    }


def serialize_owner(owner: Any) -> dict:
    """Serialize an Owner object."""
    return {
        "discord_id": owner.discord_id,
        "discord_name": owner.discord_name,
        "dollars": owner.dollars,
        "bloodskulls": owner.bloodskulls,
    }


def serialize_kennel(kennel: Any) -> dict:
    """Serialize a Kennel object."""
    return {
        "id": kennel.id,
        "owner_discord_id": kennel.owner_discord_id,
        "name": kennel.name,
        "pooch_limit": kennel.pooch_limit,
    }


def serialize_pooch_breed_info(info: Any) -> dict:
    """Serialize a PoochBreedInfo object."""
    return {
        "breed": serialize_breed(info.breed),
        "relative_weight": info.relative_weight,
    }


def serialize_pooch(pooch: Any, include_relations: bool = True) -> dict:
    """Serialize a Pooch object."""
    data = {
        "id": pooch.id,
        "name": pooch.name,
        "age": pooch.age,
        "sex": pooch.sex,
        "base_health": pooch.base_health,
        "health_loss_age": pooch.health_loss_age,
        "breeding_cooldown": pooch.breeding_cooldown,
        "alive": pooch.alive,
        "virgin": pooch.virgin,
        "owner_discord_id": pooch.owner_discord_id,
        "vendor_id": pooch.vendor_id,
        "created_at": serialize_datetime(pooch.created_at),
        "birthday": serialize_datetime(pooch.birthday),
        "health": pooch.health,
        "status": pooch.status,
        "mood": pooch.mood,
    }

    if include_relations:
        data["breeds"] = [serialize_pooch_breed_info(b) for b in pooch.breeds]
        data["mutations"] = [serialize_mutation(m) for m in pooch.mutations]
        if pooch.owner is not None:
            data["owner"] = serialize_owner(pooch.owner)

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
    }

    for mutation in [vendor.desired_mutation_1, vendor.desired_mutation_2, vendor.desired_mutation_3]:
        if mutation:
            data["desired_mutations"].append(serialize_mutation(mutation))

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


def serialize_day_change_summary(summary: Any) -> dict:
    """Serialize a DayChangeSummary object."""
    return {
        "server_discord_id": summary.server.discord_id,
        "births": [serialize_birth_event(e) for e in summary.births],
        "deaths": [serialize_death_event(e) for e in summary.deaths],
        "other_events": [serialize_other_event(e) for e in summary.other_events],
    }
