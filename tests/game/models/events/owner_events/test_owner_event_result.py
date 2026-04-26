from src.game.models.events.owner_events.owner_event_result import OwnerEventResult


class TestOwnerEventResultFromDict:
    def test_full_round_trip(self):
        data = {
            "success": True,
            "message": "It worked",
            "money_changed": 50,
            "bloodskulls_changed": 2,
            "pooches_affected": [1, 2],
            "pooches_killed": [3],
            "pooches_created": [4],
            "mutations_added": [[1, 10], [2, 20]],
            "mutations_removed": [[3, 30]],
            "extra_data": {"info": "test"},
        }
        result = OwnerEventResult.from_dict(data)
        assert result.success is True
        assert result.message == "It worked"
        assert result.money_changed == 50
        assert result.bloodskulls_changed == 2
        assert result.pooches_affected == [1, 2]
        assert result.pooches_killed == [3]
        assert result.pooches_created == [4]
        assert result.mutations_added == [(1, 10), (2, 20)]
        assert result.mutations_removed == [(3, 30)]
        assert result.extra_data == {"info": "test"}

        d = result.to_dict()
        assert d["success"] is True
        assert d["message"] == "It worked"
        assert d["mutations_added"] == [[1, 10], [2, 20]]
        assert d["mutations_removed"] == [[3, 30]]

    def test_minimal_dict_defaults(self):
        result = OwnerEventResult.from_dict({})
        assert result.success is True
        assert result.message == ""
        assert result.money_changed == 0
        assert result.bloodskulls_changed == 0
        assert result.pooches_affected == []
        assert result.pooches_killed == []
        assert result.pooches_created == []
        assert result.mutations_added == []
        assert result.mutations_removed == []
        assert result.extra_data == {}

    def test_from_dict_copies_lists(self):
        original = [1, 2]
        data = {"pooches_affected": original}
        result = OwnerEventResult.from_dict(data)
        result.pooches_affected.append(99)
        assert 99 not in original


class TestOwnerEventResultToDict:
    def test_mutations_serialized_as_lists(self):
        result = OwnerEventResult(mutations_added=[(1, 10), (2, 20)])
        d = result.to_dict()
        assert d["mutations_added"] == [[1, 10], [2, 20]]
        # Each entry should be a list, not a tuple
        assert isinstance(d["mutations_added"][0], list)

    def test_default_to_dict(self):
        result = OwnerEventResult()
        d = result.to_dict()
        assert d["success"] is True
        assert d["money_changed"] == 0


class TestOwnerEventResultMerge:
    def test_merge_money_totals(self):
        r1 = OwnerEventResult(money_changed=10, bloodskulls_changed=1)
        r2 = OwnerEventResult(money_changed=20, bloodskulls_changed=3)
        r1.merge(r2)
        assert r1.money_changed == 30
        assert r1.bloodskulls_changed == 4

    def test_merge_list_extensions(self):
        r1 = OwnerEventResult(pooches_affected=[1], pooches_killed=[2], pooches_created=[3])
        r2 = OwnerEventResult(pooches_affected=[4], pooches_killed=[5], pooches_created=[6])
        r1.merge(r2)
        assert r1.pooches_affected == [1, 4]
        assert r1.pooches_killed == [2, 5]
        assert r1.pooches_created == [3, 6]

    def test_merge_mutations_extended(self):
        r1 = OwnerEventResult(mutations_added=[(1, 10)])
        r2 = OwnerEventResult(mutations_added=[(2, 20)], mutations_removed=[(3, 30)])
        r1.merge(r2)
        assert r1.mutations_added == [(1, 10), (2, 20)]
        assert r1.mutations_removed == [(3, 30)]

    def test_merge_success_and_logic(self):
        r1 = OwnerEventResult(success=True)
        r2 = OwnerEventResult(success=False)
        r1.merge(r2)
        assert r1.success is False

    def test_merge_success_both_true(self):
        r1 = OwnerEventResult(success=True)
        r2 = OwnerEventResult(success=True)
        r1.merge(r2)
        assert r1.success is True

    def test_merge_success_both_false(self):
        r1 = OwnerEventResult(success=False)
        r2 = OwnerEventResult(success=False)
        r1.merge(r2)
        assert r1.success is False

    def test_merge_messages_combining(self):
        r1 = OwnerEventResult(message="Hello")
        r2 = OwnerEventResult(message="World")
        r1.merge(r2)
        assert r1.message == "Hello\nWorld"

    def test_merge_message_empty_other(self):
        r1 = OwnerEventResult(message="Hello")
        r2 = OwnerEventResult(message="")
        r1.merge(r2)
        assert r1.message == "Hello"

    def test_merge_message_empty_self(self):
        r1 = OwnerEventResult(message="")
        r2 = OwnerEventResult(message="World")
        r1.merge(r2)
        assert r1.message == "World"

    def test_merge_message_both_empty(self):
        r1 = OwnerEventResult(message="")
        r2 = OwnerEventResult(message="")
        r1.merge(r2)
        assert r1.message == ""

    def test_merge_extra_data_new_key(self):
        r1 = OwnerEventResult(extra_data={"a": 1})
        r2 = OwnerEventResult(extra_data={"b": 2})
        r1.merge(r2)
        assert r1.extra_data == {"a": 1, "b": 2}

    def test_merge_extra_data_dict_update(self):
        r1 = OwnerEventResult(extra_data={"nested": {"x": 1}})
        r2 = OwnerEventResult(extra_data={"nested": {"y": 2}})
        r1.merge(r2)
        assert r1.extra_data["nested"] == {"x": 1, "y": 2}

    def test_merge_extra_data_list_extend(self):
        r1 = OwnerEventResult(extra_data={"items": [1, 2]})
        r2 = OwnerEventResult(extra_data={"items": [3, 4]})
        r1.merge(r2)
        assert r1.extra_data["items"] == [1, 2, 3, 4]

    def test_merge_extra_data_scalar_overwrite(self):
        r1 = OwnerEventResult(extra_data={"count": 5})
        r2 = OwnerEventResult(extra_data={"count": 10})
        r1.merge(r2)
        assert r1.extra_data["count"] == 10

    def test_merge_returns_self(self):
        r1 = OwnerEventResult()
        r2 = OwnerEventResult()
        returned = r1.merge(r2)
        assert returned is r1

    def test_merge_preserves_original_extra_data_keys(self):
        r1 = OwnerEventResult(extra_data={"only_in_r1": "yes"})
        r2 = OwnerEventResult(extra_data={"only_in_r2": "also"})
        r1.merge(r2)
        assert "only_in_r1" in r1.extra_data
        assert "only_in_r2" in r1.extra_data
