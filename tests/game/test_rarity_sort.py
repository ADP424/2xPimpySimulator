"""Tests for src/game/rarity_sort.py."""

from types import SimpleNamespace

from src.game.utils.rarity_sort import sort_by_rarity_weight, weight_for_rarity


def test_weight_for_rarity_ordering():
    # Common is highest; unique is lowest.
    assert weight_for_rarity("common") > weight_for_rarity("uncommon")
    assert weight_for_rarity("uncommon") > weight_for_rarity("novel")
    assert weight_for_rarity("novel") > weight_for_rarity("rare")
    assert weight_for_rarity("rare") > weight_for_rarity("unprecedented")
    assert weight_for_rarity("unprecedented") > weight_for_rarity("remarkable")
    assert weight_for_rarity("remarkable") > weight_for_rarity("extraordinary")
    assert weight_for_rarity("extraordinary") > weight_for_rarity("unique")


def test_weight_for_rarity_case_insensitive():
    assert weight_for_rarity("COMMON") == weight_for_rarity("common")
    assert weight_for_rarity("Common") == weight_for_rarity("common")


def test_weight_for_rarity_unknown_sorts_last():
    assert weight_for_rarity("bogus") == 0
    assert weight_for_rarity(None) == 0


def test_sort_by_rarity_weight_default_key():
    items = [
        SimpleNamespace(name="a", rarity="unique"),
        SimpleNamespace(name="b", rarity="common"),
        SimpleNamespace(name="c", rarity="rare"),
    ]
    sorted_items = sort_by_rarity_weight(items)
    assert [i.name for i in sorted_items] == ["b", "c", "a"]


def test_sort_by_rarity_weight_stable_secondary():
    items = [
        SimpleNamespace(name="zebra", rarity="common"),
        SimpleNamespace(name="alpha", rarity="common"),
        SimpleNamespace(name="bravo", rarity="rare"),
    ]
    sorted_items = sort_by_rarity_weight(items, secondary=lambda i: i.name)
    assert [i.name for i in sorted_items] == ["alpha", "zebra", "bravo"]


def test_sort_by_rarity_weight_custom_key():
    items = [
        {"label": "x", "r": "rare"},
        {"label": "y", "r": "common"},
    ]
    sorted_items = sort_by_rarity_weight(items, key=lambda i: i["r"])
    assert [i["label"] for i in sorted_items] == ["y", "x"]


def test_sort_by_rarity_weight_empty_input():
    assert sort_by_rarity_weight([]) == []


def test_sort_by_rarity_weight_does_not_mutate_input():
    original = [
        SimpleNamespace(name="a", rarity="unique"),
        SimpleNamespace(name="b", rarity="common"),
    ]
    sort_by_rarity_weight(original)
    # Order unchanged.
    assert [i.name for i in original] == ["a", "b"]
