from src.game.models.events.owner_events.owner_event_context import OwnerEventContext


class TestOwnerEventContextFromDict:
    def test_full_round_trip(self):
        data = {
            "owner_discord_id": 123,
            "affected_pooch_ids": [1, 2, 3],
            "affected_kennel_ids": [10],
            "selected_pooch_id": 2,
            "selected_kennel_id": 10,
            "extra_data": {"key": "value"},
        }
        ctx = OwnerEventContext.from_dict(data)
        assert ctx.owner_discord_id == 123
        assert ctx.affected_pooch_ids == [1, 2, 3]
        assert ctx.affected_kennel_ids == [10]
        assert ctx.selected_pooch_id == 2
        assert ctx.selected_kennel_id == 10
        assert ctx.extra_data == {"key": "value"}

        result = ctx.to_dict()
        assert result == data

    def test_minimal_dict(self):
        ctx = OwnerEventContext.from_dict({})
        assert ctx.owner_discord_id == 0
        assert ctx.affected_pooch_ids == []
        assert ctx.affected_kennel_ids == []
        assert ctx.selected_pooch_id is None
        assert ctx.selected_kennel_id is None
        assert ctx.extra_data == {}

    def test_partial_dict(self):
        ctx = OwnerEventContext.from_dict({"owner_discord_id": 42, "selected_pooch_id": 7})
        assert ctx.owner_discord_id == 42
        assert ctx.selected_pooch_id == 7
        assert ctx.affected_pooch_ids == []
        assert ctx.selected_kennel_id is None

    def test_to_dict_preserves_none_values(self):
        ctx = OwnerEventContext(owner_discord_id=1)
        d = ctx.to_dict()
        assert d["selected_pooch_id"] is None
        assert d["selected_kennel_id"] is None

    def test_from_dict_copies_lists(self):
        """Ensure lists are independent copies, not references to the input."""
        original_ids = [1, 2, 3]
        data = {"affected_pooch_ids": original_ids}
        ctx = OwnerEventContext.from_dict(data)
        ctx.affected_pooch_ids.append(99)
        assert 99 not in original_ids

    def test_from_dict_copies_extra_data(self):
        """Ensure extra_data is a copy, not a reference."""
        original_extra = {"key": "value"}
        data = {"extra_data": original_extra}
        ctx = OwnerEventContext.from_dict(data)
        ctx.extra_data["new_key"] = "new_value"
        assert "new_key" not in original_extra


class TestOwnerEventContextDefaults:
    def test_default_construction(self):
        ctx = OwnerEventContext(owner_discord_id=42)
        assert ctx.owner_discord_id == 42
        assert ctx.affected_pooch_ids == []
        assert ctx.affected_kennel_ids == []
        assert ctx.selected_pooch_id is None
        assert ctx.selected_kennel_id is None
        assert ctx.extra_data == {}

    def test_mutable_fields_are_independent(self):
        """Ensure default factory lists are not shared between instances."""
        c1 = OwnerEventContext(owner_discord_id=1)
        c2 = OwnerEventContext(owner_discord_id=2)
        c1.affected_pooch_ids.append(99)
        assert c2.affected_pooch_ids == []


class TestOwnerEventContextRoundTrip:
    def test_complex_extra_data(self):
        ctx = OwnerEventContext(
            owner_discord_id=10,
            extra_data={"nested": {"a": 1}, "list_val": [1, 2, 3]},
        )
        d = ctx.to_dict()
        restored = OwnerEventContext.from_dict(d)
        assert restored.extra_data == {"nested": {"a": 1}, "list_val": [1, 2, 3]}

    def test_empty_lists_survive_round_trip(self):
        ctx = OwnerEventContext(owner_discord_id=5)
        d = ctx.to_dict()
        restored = OwnerEventContext.from_dict(d)
        assert restored.affected_pooch_ids == []
        assert restored.affected_kennel_ids == []
