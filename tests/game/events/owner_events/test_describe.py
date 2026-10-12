"""Tests for src/game/events/owner_events/describe.py."""

from __future__ import annotations

from src.game.events.owner_events import describe_owner_event_result
from src.game.models.events.owner_events import (
    OwnerEventEntityReferences,
    OwnerEventResult,
)
from src.game.models.events.owner_events.owner_event_entity_reference import (
    OwnerEventEntityReference,
)


def _refs() -> OwnerEventEntityReferences:
    refs = OwnerEventEntityReferences()
    refs.pooches.append(OwnerEventEntityReference(id=1, label="Buddy"))
    return refs


class TestDescribeOwnerEventResult:
    def test_none_result_is_empty(self):
        description = describe_owner_event_result(None)
        assert description.headline is None
        assert description.lines == []

    def test_headline_is_selected_outcome_message_without_chance(self):
        result = OwnerEventResult(extra_data={"selected_outcome": {"message": "Lucky!", "chance": 0.25}})
        description = describe_owner_event_result(result)
        assert description.headline == "Lucky!"
        assert all("0.25" not in line for line in description.lines)

    def test_headline_falls_back_to_description(self):
        result = OwnerEventResult(extra_data={"selected_outcome": {"description": "Desc."}})
        assert describe_owner_event_result(result).headline == "Desc."

    def test_action_log_in_execution_order_with_names(self):
        result = OwnerEventResult(
            message="Done.",
            extra_data={
                "action_log": [
                    {"type": "bloodskulls_changes", "amount": -1},
                    {"type": "money_changes", "amount": 20},
                    {"type": "health_changes", "pooch_id": 1, "amount": -2},
                    {"type": "unknown_kind"},
                ],
                "started_events": [{"name": "Chain"}],
            },
        )
        description = describe_owner_event_result(result, _refs())
        assert description.lines == [
            "Done.",
            "Bloodskulls: -1",
            "Dollars: +20",
            "Health: Buddy -2",
            "Started event: Chain",
        ]

    def test_unknown_pooch_falls_back_to_id(self):
        result = OwnerEventResult(extra_data={"action_log": [{"type": "killed_pooches", "pooch_id": 9}]})
        assert describe_owner_event_result(result, _refs()).lines == ["Lost pooch: Pooch #9"]

    def test_fight_result_rendered_after_action_log(self):
        result = OwnerEventResult(
            extra_data={
                "action_log": [{"type": "money_changes", "amount": 5}],
                "fight_result": {"attacker_id": 1, "defender_id": 2, "winner_id": 1, "rounds_fought": 3},
            }
        )
        assert describe_owner_event_result(result, _refs()).lines == [
            "Dollars: +5",
            "Fight: Buddy defeated Pooch #2 (3 rounds)",
        ]

    def test_legacy_buckets_in_fixed_order(self):
        result = OwnerEventResult(
            money_changed=10,
            pooches_killed=[3],
            extra_data={"health_changes": {"1": 4}, "kennels_deleted": [5]},
        )
        assert describe_owner_event_result(result, _refs()).lines == [
            "Dollars: +10",
            "Pooches lost: 1",
            "Health: Buddy +4",
            "Kennel deleted: Kennel #5",
        ]

    def test_empty_result_has_no_lines(self):
        description = describe_owner_event_result(OwnerEventResult())
        assert description.headline is None
        assert description.lines == []
