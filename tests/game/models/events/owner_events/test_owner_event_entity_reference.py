from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.models.events.owner_events.owner_event_context import OwnerEventContext
from src.game.models.events.owner_events.owner_event_entity_reference import (
    OwnerEventEntityReference,
    OwnerEventEntityReferences,
    _iter_dict_entries,
    _normalize_detail_entries,
    resolve_owner_event_entity_references,
)
from src.game.models.events.owner_events.owner_event_result import OwnerEventResult


class TestOwnerEventEntityReference:
    def test_creation_with_description(self):
        ref = OwnerEventEntityReference(id=1, label="Fido", description="A good boy")
        assert ref.id == 1
        assert ref.label == "Fido"
        assert ref.description == "A good boy"

    def test_creation_without_description(self):
        ref = OwnerEventEntityReference(id=2, label="Rex")
        assert ref.id == 2
        assert ref.label == "Rex"
        assert ref.description is None


class TestOwnerEventEntityReferencesForKind:
    def test_for_kind_pooches(self):
        ref = OwnerEventEntityReference(id=1, label="Fido")
        refs = OwnerEventEntityReferences(pooches=[ref])
        assert refs.for_kind("pooches") == [ref]

    def test_for_kind_breeds(self):
        ref = OwnerEventEntityReference(id=1, label="Lab")
        refs = OwnerEventEntityReferences(breeds=[ref])
        assert refs.for_kind("breeds") == [ref]

    def test_for_kind_mutations(self):
        ref = OwnerEventEntityReference(id=1, label="Cataracts")
        refs = OwnerEventEntityReferences(mutations=[ref])
        assert refs.for_kind("mutations") == [ref]

    def test_for_kind_returns_same_list_object(self):
        refs = OwnerEventEntityReferences()
        assert refs.for_kind("pooches") is refs.pooches


class TestOwnerEventEntityReferencesAdd:
    def test_add_new_reference(self):
        refs = OwnerEventEntityReferences()
        ref = OwnerEventEntityReference(id=1, label="Fido")
        refs.add("pooches", ref)
        assert len(refs.pooches) == 1
        assert refs.pooches[0].id == 1

    def test_add_deduplicates_by_id(self):
        refs = OwnerEventEntityReferences()
        ref1 = OwnerEventEntityReference(id=1, label="Fido")
        ref2 = OwnerEventEntityReference(id=1, label="Fido Updated")
        refs.add("pooches", ref1)
        refs.add("pooches", ref2)
        assert len(refs.pooches) == 1
        assert refs.pooches[0].label == "Fido"  # first one kept

    def test_add_different_ids(self):
        refs = OwnerEventEntityReferences()
        refs.add("breeds", OwnerEventEntityReference(id=1, label="Lab"))
        refs.add("breeds", OwnerEventEntityReference(id=2, label="Pug"))
        assert len(refs.breeds) == 2

    def test_add_to_different_kinds(self):
        refs = OwnerEventEntityReferences()
        refs.add("pooches", OwnerEventEntityReference(id=1, label="Fido"))
        refs.add("mutations", OwnerEventEntityReference(id=1, label="Cataracts"))
        assert len(refs.pooches) == 1
        assert len(refs.mutations) == 1


class TestOwnerEventEntityReferencesCopy:
    def test_copy_is_independent(self):
        refs = OwnerEventEntityReferences(
            pooches=[OwnerEventEntityReference(id=1, label="Fido")],
            breeds=[OwnerEventEntityReference(id=10, label="Lab")],
        )
        copied = refs.copy()

        # Verify data matches
        assert len(copied.pooches) == 1
        assert copied.pooches[0].id == 1
        assert len(copied.breeds) == 1
        assert copied.breeds[0].id == 10

        # Modifying copy should not affect original
        copied.pooches.append(OwnerEventEntityReference(id=2, label="Rex"))
        assert len(refs.pooches) == 1

    def test_copy_of_empty(self):
        refs = OwnerEventEntityReferences()
        copied = refs.copy()
        assert not copied.has_items()
        copied.add("pooches", OwnerEventEntityReference(id=1, label="X"))
        assert not refs.has_items()


class TestOwnerEventEntityReferencesHasItems:
    def test_empty_has_no_items(self):
        refs = OwnerEventEntityReferences()
        assert refs.has_items() is False

    def test_has_items_with_pooches(self):
        refs = OwnerEventEntityReferences(pooches=[OwnerEventEntityReference(id=1, label="X")])
        assert refs.has_items() is True

    def test_has_items_with_breeds(self):
        refs = OwnerEventEntityReferences(breeds=[OwnerEventEntityReference(id=1, label="X")])
        assert refs.has_items() is True

    def test_has_items_with_mutations(self):
        refs = OwnerEventEntityReferences(mutations=[OwnerEventEntityReference(id=1, label="X")])
        assert refs.has_items() is True


class TestNormalizeDetailEntries:
    def test_list_of_dicts_passed_through(self):
        entries = [{"pooch_id": 1, "amount": 5}, {"pooch_id": 2, "amount": 3}]
        result = _normalize_detail_entries(entries, id_key="pooch_id", value_key="amount")
        assert result == entries

    def test_list_with_non_dict_entries_filtered(self):
        entries = [{"pooch_id": 1, "amount": 5}, "not_a_dict", 42]
        result = _normalize_detail_entries(entries, id_key="pooch_id", value_key="amount")
        assert len(result) == 1
        assert result[0]["pooch_id"] == 1

    def test_dict_converted_to_list(self):
        data = {1: 5, 2: 10}
        result = _normalize_detail_entries(data, id_key="pooch_id", value_key="amount")
        assert len(result) == 2
        ids = {entry["pooch_id"] for entry in result}
        amounts = {entry["amount"] for entry in result}
        assert ids == {1, 2}
        assert amounts == {5, 10}

    def test_none_returns_empty(self):
        result = _normalize_detail_entries(None, id_key="pooch_id", value_key="amount")
        assert result == []

    def test_empty_list_returns_empty(self):
        result = _normalize_detail_entries([], id_key="pooch_id", value_key="amount")
        assert result == []

    def test_empty_dict_returns_empty(self):
        result = _normalize_detail_entries({}, id_key="pooch_id", value_key="amount")
        assert result == []

    def test_non_iterable_returns_empty(self):
        result = _normalize_detail_entries(42, id_key="pooch_id", value_key="amount")
        assert result == []

    def test_string_returns_empty(self):
        result = _normalize_detail_entries("not valid", id_key="pooch_id", value_key="amount")
        assert result == []


class TestIterDictEntries:
    def test_list_of_dicts(self):
        result = _iter_dict_entries([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_list_filters_non_dicts(self):
        result = _iter_dict_entries([{"a": 1}, "nope", 42, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_none_returns_empty(self):
        assert _iter_dict_entries(None) == []

    def test_non_list_returns_empty(self):
        assert _iter_dict_entries(42) == []
        assert _iter_dict_entries("str") == []
        assert _iter_dict_entries({}) == []


class TestResolveOwnerEventEntityReferences:
    @pytest.mark.asyncio
    async def test_empty_context_returns_empty_refs(self):
        context = OwnerEventContext(owner_discord_id=1)
        with (
            patch(
                "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            refs = await resolve_owner_event_entity_references(context)
        assert not refs.has_items()

    @pytest.mark.asyncio
    async def test_resolves_pooch_from_context_affected(self):
        context = OwnerEventContext(owner_discord_id=1)
        context.affected_pooch_ids = [42]
        fake_pooch = SimpleNamespace(name="Buddy")
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=fake_pooch),
        ):
            refs = await resolve_owner_event_entity_references(context)
        assert len(refs.pooches) == 1
        assert refs.pooches[0].id == 42
        assert refs.pooches[0].label == "Buddy"

    @pytest.mark.asyncio
    async def test_resolves_selected_pooch(self):
        context = OwnerEventContext(owner_discord_id=1)
        context.selected_pooch_id = 7
        fake_pooch = SimpleNamespace(name="Rex")
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=fake_pooch),
        ):
            refs = await resolve_owner_event_entity_references(context)
        assert len(refs.pooches) == 1
        assert refs.pooches[0].label == "Rex"

    @pytest.mark.asyncio
    async def test_pooch_not_found_uses_fallback_label(self):
        context = OwnerEventContext(owner_discord_id=1)
        context.affected_pooch_ids = [99]
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=None),
        ):
            refs = await resolve_owner_event_entity_references(context)
        assert refs.pooches[0].label == "Pooch #99"

    @pytest.mark.asyncio
    async def test_resolves_mutations_from_result(self):
        context = OwnerEventContext(owner_discord_id=1)
        result = OwnerEventResult()
        result.mutations_added = [(1, 5)]
        fake_mut = SimpleNamespace(name="Cataracts")
        with (
            patch(
                "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
                new=AsyncMock(return_value=SimpleNamespace(name="P")),
            ),
            patch(
                "src.game.models.events.owner_events.owner_event_entity_reference.get_mutation_by_id",
                new=AsyncMock(return_value=fake_mut),
            ),
        ):
            refs = await resolve_owner_event_entity_references(context, result=result)
        assert len(refs.mutations) == 1
        assert refs.mutations[0].label == "Cataracts"

    @pytest.mark.asyncio
    async def test_resolves_breeds_from_extra_data(self):
        context = OwnerEventContext(owner_discord_id=1)
        result = OwnerEventResult()
        result.extra_data = {"breeds_added": [{"pooch_id": 1, "breed_id": 10}]}
        fake_breed = SimpleNamespace(name="Labrador")
        with (
            patch(
                "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
                new=AsyncMock(return_value=SimpleNamespace(name="P")),
            ),
            patch(
                "src.game.models.events.owner_events.owner_event_entity_reference.get_breed_by_id",
                new=AsyncMock(return_value=fake_breed),
            ),
        ):
            refs = await resolve_owner_event_entity_references(context, result=result)
        assert len(refs.breeds) == 1
        assert refs.breeds[0].label == "Labrador"

    @pytest.mark.asyncio
    async def test_deduplicates_pooch_ids(self):
        context = OwnerEventContext(owner_discord_id=1)
        context.affected_pooch_ids = [1, 1]
        context.selected_pooch_id = 1
        result = OwnerEventResult()
        result.pooches_affected = [1]
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=SimpleNamespace(name="X")),
        ) as mock_get:
            refs = await resolve_owner_event_entity_references(context, result=result)
        assert len(refs.pooches) == 1
        mock_get.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_preserves_existing_references(self):
        context = OwnerEventContext(owner_discord_id=1)
        context.affected_pooch_ids = [2]
        existing = OwnerEventEntityReferences(pooches=[OwnerEventEntityReference(id=1, label="Already")])
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=SimpleNamespace(name="New")),
        ):
            refs = await resolve_owner_event_entity_references(context, existing=existing)
        assert len(refs.pooches) == 2
        assert refs.pooches[0].label == "Already"
        assert refs.pooches[1].label == "New"

    @pytest.mark.asyncio
    async def test_skips_already_seen_ids_from_existing(self):
        context = OwnerEventContext(owner_discord_id=1)
        context.affected_pooch_ids = [1]
        existing = OwnerEventEntityReferences(pooches=[OwnerEventEntityReference(id=1, label="Already")])
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=SimpleNamespace(name="New")),
        ) as mock_get:
            refs = await resolve_owner_event_entity_references(context, existing=existing)
        assert len(refs.pooches) == 1
        mock_get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_health_changes_dict_format(self):
        context = OwnerEventContext(owner_discord_id=1)
        result = OwnerEventResult()
        result.extra_data = {"health_changes": {5: -3}}
        with patch(
            "src.game.models.events.owner_events.owner_event_entity_reference.get_pooch_by_id",
            new=AsyncMock(return_value=SimpleNamespace(name="Hurt")),
        ):
            refs = await resolve_owner_event_entity_references(context, result=result)
        assert any(p.id == 5 for p in refs.pooches)
