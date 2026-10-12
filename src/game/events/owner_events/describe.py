"""
Plain-text description of an owner event result, shared by the bot and the web.

Frontends add their own formatting (the bot italicises the headline and truncates to an embed field).
The outcome ``chance`` and other raw ``extra_data`` never leave this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.game.models.events.owner_events import (
    OwnerEventEntityReferences,
    OwnerEventResult,
    normalize_detail_entries,
)


@dataclass
class OwnerEventResultDescription:
    """The selected outcome's message (if any) plus one plain-text line per visible effect, in display order."""

    headline: Optional[str] = None
    lines: list[str] = field(default_factory=list)


# Legacy (pre-action_log) buckets stored as lists of dicts, in the order they are rendered.
_LEGACY_LIST_BUCKETS_BEFORE_CREATED = ("released_strays", "received_strays", "created_pooches", "bought_pooches")
_LEGACY_LIST_BUCKETS_AFTER_KILLED = (
    "sold_pooches",
    "stat_changes",
)
_LEGACY_LIST_BUCKETS_AFTER_AGE = (
    "breeding_cooldown_changes",
    "renamed_pooches",
    "transferred_pooches",
)


def _signed(value: int) -> str:
    return f"{value:+d}"


def describe_owner_event_result(
    result: Optional[OwnerEventResult],
    entity_references: Optional[OwnerEventEntityReferences] = None,
) -> OwnerEventResultDescription:
    """
    Describe what an owner event result did, for display to the owner.

    Parameters
    ----------
    result: OwnerEventResult, optional
        The stored result of the event. None yields an empty description.

    entity_references: OwnerEventEntityReferences, optional
        Resolved references used to turn pooch IDs into names.

    Returns
    -------
    OwnerEventResultDescription
        The headline (selected outcome message) and the detail lines.
    """

    description = OwnerEventResultDescription()
    if result is None:
        return description

    extra_data = result.extra_data or {}

    def _pooch_name(pooch_id: Any) -> str:
        if entity_references is not None:
            for ref in entity_references.pooches:
                if ref.id == pooch_id or str(ref.id) == str(pooch_id):
                    return ref.label
        return f"Pooch #{pooch_id}"

    def _entry_pooch_name(entry: dict) -> str:
        return entry.get("pooch_name") or _pooch_name(entry.get("pooch_id", "?"))

    selected_outcome = extra_data.get("selected_outcome")
    if isinstance(selected_outcome, dict):
        description.headline = selected_outcome.get("message") or selected_outcome.get("description") or None

    lines: list[str] = []
    if result.message:
        lines.append(result.message)

    def _fmt_entry(entry: dict) -> Optional[str]:
        """Format a single action_log entry. Returns None if nothing to show."""
        kind = entry.get("type", "")
        if kind == "money_changes":
            return f"Dollars: {entry.get('amount', 0):+d}"
        if kind == "bloodskulls_changes":
            return f"Bloodskulls: {entry.get('amount', 0):+d}"
        if kind == "released_strays":
            return f"Released as stray: {_entry_pooch_name(entry)}"
        if kind == "received_strays":
            kennel_name = entry.get("kennel_name")
            suffix = f" (kennel {kennel_name})" if kennel_name else ""
            return f"Taken in: {_entry_pooch_name(entry)}{suffix}"
        if kind == "created_pooches":
            text = f"Created pooch: {_entry_pooch_name(entry)}"
            extras: list[str] = []
            if entry.get("sex"):
                extras.append(str(entry["sex"]).capitalize())
            if entry.get("age") is not None:
                extras.append(f"age {entry['age']}")
            if entry.get("kennel_name"):
                extras.append(f"kennel {entry['kennel_name']}")
            if extras:
                text += f" ({', '.join(extras)})"
            return text
        if kind == "bought_pooches":
            parts: list[str] = []
            if entry.get("price") is not None:
                parts.append(f"${entry['price']}")
            if entry.get("kennel_name"):
                parts.append(f"in {entry['kennel_name']}")
            return f"Bought: {_entry_pooch_name(entry)}" + (f" ({', '.join(parts)})" if parts else "")
        if kind == "sold_pooches":
            price = entry.get("price")
            return f"Sold: {_entry_pooch_name(entry)}" + (f" (${price})" if price is not None else "")
        if kind == "killed_pooches":
            return f"Lost pooch: {_entry_pooch_name(entry)}"
        if kind == "stat_changes":
            name = _entry_pooch_name(entry)
            stat = str(entry.get("stat", "stat")).capitalize()
            amount = entry.get("amount", 0)
            if entry.get("mode") == "set":
                return f"{stat}: {name} set to {amount}"
            return f"{stat}: {name} {_signed(amount)}"
        if kind == "health_changes":
            suffix = f" (base now {entry['new_base_health']})" if entry.get("new_base_health") is not None else ""
            return f"Health: {_entry_pooch_name(entry)} {_signed(entry.get('amount', 0))}{suffix}"
        if kind == "age_changes":
            suffix = f" (now age {entry['new_age']})" if entry.get("new_age") is not None else ""
            return f"Age: {_entry_pooch_name(entry)} {_signed(entry.get('amount', 0))}{suffix}"
        if kind == "breeding_cooldown_changes":
            return f"Breeding cooldown: {_entry_pooch_name(entry)} set to {entry.get('cooldown', 0)}"
        if kind == "renamed_pooches":
            return f"Renamed: {entry.get('old_name', 'Unknown')} → {entry.get('new_name', 'Unknown')}"
        if kind == "transferred_pooches":
            return f"Transferred: {_entry_pooch_name(entry)} → {entry.get('destination') or 'new owner'}"
        if kind == "mutations_added_details":
            return f"Mutation gained: {entry.get('pooch_name', 'Unknown')} → {entry.get('mutation_name', 'Unknown')}"
        if kind == "mutations_removed_details":
            return f"Mutation removed: {entry.get('pooch_name', 'Unknown')} → {entry.get('mutation_name', 'Unknown')}"
        if kind == "breeds_added":
            weight = entry.get("weight")
            suffix = f" ({round(float(weight * 100))}% weight)" if weight is not None else ""
            return f"Breed added: {entry.get('pooch_name', 'Unknown')} → {entry.get('breed_name', 'Unknown')}{suffix}"
        if kind == "breeds_removed":
            return f"Breed removed: {_entry_pooch_name(entry)} → {entry.get('breed_name') or 'Unknown breed'}"
        if kind == "injuries_added":
            return f"Injured: {_entry_pooch_name(entry)} ({entry.get('injury_name') or 'Unknown injury'})"
        if kind == "kennel_capacity_changes":
            name = entry.get("kennel_name") or f"Kennel #{entry.get('kennel_id', '?')}"
            suffix = f" (limit {entry['new_limit']})" if entry.get("new_limit") is not None else ""
            return f"Kennel capacity: {name} {_signed(entry.get('amount', 0))}{suffix}"
        if kind == "kennel_upgrade_tier_changes":
            return f"Kennel upgraded: Kennel #{entry.get('kennel_id', '?')} {_signed(entry.get('amount', 0))} tier(s)"
        if kind == "kennels_deleted":
            return f"Kennel deleted: Kennel #{entry.get('kennel_id', '?')}"
        return None

    def _add_bucket(kind: str) -> None:
        for entry in extra_data.get(kind, []):
            if isinstance(entry, dict):
                lines.append(_fmt_entry({"type": kind, **entry}) or "")

    def _add_detail_bucket(kind: str, id_key: str) -> None:
        for entry in normalize_detail_entries(extra_data.get(kind), id_key=id_key, value_key="amount"):
            lines.append(_fmt_entry({"type": kind, **entry}) or "")

    def _add_fight_result() -> None:
        fight_result = extra_data.get("fight_result")
        if not isinstance(fight_result, dict):
            return
        attacker_id = fight_result.get("attacker_id")
        defender_id = fight_result.get("defender_id")
        winner_id = fight_result.get("winner_id")
        rounds = fight_result.get("rounds_fought", 0)
        att_name = _pooch_name(attacker_id) if attacker_id is not None else "Attacker"
        def_name = _pooch_name(defender_id) if defender_id is not None else "Defender"
        if fight_result.get("draw", False):
            lines.append(f"Fight: {att_name} vs {def_name} — Draw ({rounds} rounds)")
        elif winner_id == attacker_id:
            lines.append(f"Fight: {att_name} defeated {def_name} ({rounds} rounds)")
        elif winner_id == defender_id:
            lines.append(f"Fight: {def_name} defeated {att_name} ({rounds} rounds)")
        else:
            lines.append(f"Fight: {att_name} vs {def_name} ({rounds} rounds)")

    action_log = extra_data.get("action_log")
    if action_log:
        # Render in execution order; fight_result is stored separately, not in action_log
        for entry in action_log:
            if isinstance(entry, dict):
                line = _fmt_entry(entry)
                if line:
                    lines.append(line)
        _add_fight_result()
    else:
        # Legacy path: results stored before action_log existed, rendered per bucket in a fixed order
        if result.money_changed:
            lines.append(f"Dollars: {result.money_changed:+d}")
        if result.bloodskulls_changed:
            lines.append(f"Bloodskulls: {result.bloodskulls_changed:+d}")
        for kind in _LEGACY_LIST_BUCKETS_BEFORE_CREATED:
            _add_bucket(kind)
        if result.pooches_created and not any(
            extra_data.get(k) for k in ("created_pooches", "bought_pooches", "received_strays")
        ):
            lines.append(f"Pooches created: {len(result.pooches_created)}")
        _add_bucket("killed_pooches")
        if result.pooches_killed and not extra_data.get("killed_pooches"):
            lines.append(f"Pooches lost: {len(result.pooches_killed)}")
        for kind in _LEGACY_LIST_BUCKETS_AFTER_KILLED:
            _add_bucket(kind)
        _add_detail_bucket("health_changes", "pooch_id")
        _add_detail_bucket("age_changes", "pooch_id")
        for kind in _LEGACY_LIST_BUCKETS_AFTER_AGE:
            _add_bucket(kind)
        _add_bucket("mutations_added_details")
        if result.mutations_added and not extra_data.get("mutations_added_details"):
            lines.append(f"Mutations added: {len(result.mutations_added)}")
        _add_bucket("mutations_removed_details")
        if result.mutations_removed and not extra_data.get("mutations_removed_details"):
            lines.append(f"Mutations removed: {len(result.mutations_removed)}")
        _add_bucket("breeds_added")
        _add_bucket("breeds_removed")
        _add_bucket("injuries_added")
        _add_detail_bucket("kennel_capacity_changes", "kennel_id")
        for kennel_id, amount in (extra_data.get("kennel_upgrade_tier_changes") or {}).items():
            lines.append(
                _fmt_entry({"type": "kennel_upgrade_tier_changes", "kennel_id": kennel_id, "amount": amount}) or ""
            )
        for kennel_id in extra_data.get("kennels_deleted") or []:
            lines.append(_fmt_entry({"type": "kennels_deleted", "kennel_id": kennel_id}) or "")
        _add_fight_result()

    description.lines = [line for line in lines if line]

    # Started (chain) events are always listed last
    for entry in extra_data.get("started_events") or []:
        if isinstance(entry, dict):
            description.lines.append(f"Started event: {entry.get('name') or 'Unknown event'}")

    return description
