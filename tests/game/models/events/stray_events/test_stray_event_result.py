from src.game.models.events.stray_events.stray_event_result import StrayEventResult


class TestStrayEventResultCreation:
    def test_defaults(self):
        r = StrayEventResult()
        assert r.success is True
        assert r.pooches_affected == []
        assert r.pooches_killed == []
        assert r.pooches_created == []
        assert r.extra_data == {}

    def test_custom_values(self):
        r = StrayEventResult(
            success=False,
            pooches_affected=[1],
            pooches_killed=[2],
            pooches_created=[3],
            extra_data={"key": "value"},
        )
        assert r.success is False
        assert r.pooches_affected == [1]
        assert r.pooches_killed == [2]
        assert r.pooches_created == [3]
        assert r.extra_data == {"key": "value"}


class TestStrayEventResultMerge:
    def test_merge_success_both_true(self):
        r1 = StrayEventResult(success=True)
        r2 = StrayEventResult(success=True)
        r1.merge(r2)
        assert r1.success is True

    def test_merge_success_other_false(self):
        r1 = StrayEventResult(success=True)
        r2 = StrayEventResult(success=False)
        r1.merge(r2)
        assert r1.success is False

    def test_merge_success_self_false(self):
        r1 = StrayEventResult(success=False)
        r2 = StrayEventResult(success=True)
        r1.merge(r2)
        assert r1.success is False

    def test_merge_success_both_false(self):
        r1 = StrayEventResult(success=False)
        r2 = StrayEventResult(success=False)
        r1.merge(r2)
        assert r1.success is False

    def test_merge_pooches_affected(self):
        r1 = StrayEventResult(pooches_affected=[1, 2])
        r2 = StrayEventResult(pooches_affected=[3])
        r1.merge(r2)
        assert r1.pooches_affected == [1, 2, 3]

    def test_merge_pooches_killed(self):
        r1 = StrayEventResult(pooches_killed=[10])
        r2 = StrayEventResult(pooches_killed=[20, 30])
        r1.merge(r2)
        assert r1.pooches_killed == [10, 20, 30]

    def test_merge_pooches_created(self):
        r1 = StrayEventResult(pooches_created=[])
        r2 = StrayEventResult(pooches_created=[5])
        r1.merge(r2)
        assert r1.pooches_created == [5]

    def test_merge_extra_data_new_key(self):
        r1 = StrayEventResult(extra_data={"a": 1})
        r2 = StrayEventResult(extra_data={"b": 2})
        r1.merge(r2)
        assert r1.extra_data == {"a": 1, "b": 2}

    def test_merge_extra_data_list_extend(self):
        r1 = StrayEventResult(extra_data={"items": [1, 2]})
        r2 = StrayEventResult(extra_data={"items": [3, 4]})
        r1.merge(r2)
        assert r1.extra_data["items"] == [1, 2, 3, 4]

    def test_merge_extra_data_scalar_overwrite(self):
        r1 = StrayEventResult(extra_data={"count": 5})
        r2 = StrayEventResult(extra_data={"count": 10})
        r1.merge(r2)
        assert r1.extra_data["count"] == 10

    def test_merge_extra_data_dict_not_extended(self):
        """When both have dicts for the same key, stray merge overwrites (unlike owner merge)."""
        r1 = StrayEventResult(extra_data={"nested": {"x": 1}})
        r2 = StrayEventResult(extra_data={"nested": {"y": 2}})
        r1.merge(r2)
        # Stray merge uses simple overwrite for non-list types
        assert r1.extra_data["nested"] == {"y": 2}

    def test_merge_returns_none(self):
        """Stray merge returns None (in-place mutation, no return)."""
        r1 = StrayEventResult()
        r2 = StrayEventResult()
        returned = r1.merge(r2)
        assert returned is None

    def test_merge_empty_into_populated(self):
        r1 = StrayEventResult(
            pooches_affected=[1],
            pooches_killed=[2],
            pooches_created=[3],
            extra_data={"k": "v"},
        )
        r2 = StrayEventResult()
        r1.merge(r2)
        assert r1.pooches_affected == [1]
        assert r1.pooches_killed == [2]
        assert r1.pooches_created == [3]
        assert r1.extra_data == {"k": "v"}

    def test_merge_populated_into_empty(self):
        r1 = StrayEventResult()
        r2 = StrayEventResult(
            pooches_affected=[1],
            pooches_killed=[2],
            pooches_created=[3],
            extra_data={"k": "v"},
        )
        r1.merge(r2)
        assert r1.pooches_affected == [1]
        assert r1.pooches_killed == [2]
        assert r1.pooches_created == [3]
        assert r1.extra_data == {"k": "v"}

    def test_merge_mixed_list_and_nonlist_extra_data(self):
        """List key in self but scalar key in other for different keys."""
        r1 = StrayEventResult(extra_data={"events": [1], "count": 5})
        r2 = StrayEventResult(extra_data={"events": [2], "status": "ok"})
        r1.merge(r2)
        assert r1.extra_data["events"] == [1, 2]
        assert r1.extra_data["count"] == 5
        assert r1.extra_data["status"] == "ok"
