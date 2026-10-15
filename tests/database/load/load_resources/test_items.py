"""Tests for src/database/load/load_resources/items.py and cross_refs.py."""

from types import SimpleNamespace

import pytest

from src.database.load.load_resources.cross_refs import find_cross_reference_errors
from src.database.load.load_resources.items import _ITEMS_ROOT, validate_items_json
from src.database.load.load_resources.utils import (
    ResourceValidationError,
    load_categorized_resource_objects,
)


def _valid():
    return {
        "Cleaning": {"Soap": {"parameters": {"price": 5, "mess_reduction": 10}}},
        "Food": {"Kibble": {"rarity": "common", "parameters": {"price": 5, "food_units": 20, "strength_add": 1}}},
    }


class TestValidateItemsJson:
    def test_shipped_items_are_valid(self):
        validate_items_json(load_categorized_resource_objects(_ITEMS_ROOT, "item"))

    def test_valid_items_pass(self):
        validate_items_json(_valid())

    @pytest.mark.parametrize(
        ("category", "item", "parameters", "message"),
        [
            ("Toys", "Ball", {"price": 1}, "unknown category"),
            ("Cleaning", "Soap", {"price": 5}, "mess_reduction: required"),
            ("Food", "Kibble", {"price": 5}, "food_units: required"),
            ("Food", "Kibble", {"price": 5, "food_units": 0}, "food_units: must be > 0"),
            ("Food", "Kibble", {"price": -1, "food_units": 5}, "price: must be >= 0"),
            ("Food", "Kibble", {"price": 5, "food_units": 5, "size_add": 1}, "unknown keys: size_add"),
            ("Food", "Kibble", {"price": 5, "food_units": 5, "strength_mult": 2}, "unknown keys: strength_mult"),
        ],
    )
    def test_invalid_items_fail(self, category, item, parameters, message):
        with pytest.raises(ResourceValidationError, match=message):
            validate_items_json({category: {item: {"parameters": parameters}}})


def _mutation(name, **parameters):
    return SimpleNamespace(name=name, parameters=parameters)


class TestFindCrossReferenceErrors:
    def test_known_names_pass_case_insensitively(self):
        mutations = [
            _mutation("Albinism"),
            _mutation(
                "Razor Tail",
                incompatible_mutations=["albinism"],
                disease_immunities=["MANGE"],
                on_death_triggers=[{"on_death": "injure", "on_death_options": ["minor scratch"]}],
            ),
        ]
        assert find_cross_reference_errors(mutations, {"mange"}, {"minor scratch"}) == []

    def test_unknown_names_are_reported(self):
        mutations = [
            _mutation(
                "Razor Tail",
                incompatible_mutations=["Ghost"],
                disease_predispositions=["Plague"],
                on_death_triggers=[{"on_death": "injure", "on_death_options": ["Paper Cut"]}],
            )
        ]
        errors = find_cross_reference_errors(mutations, {"mange"}, {"minor scratch"})
        assert errors == [
            "mutation.Razor Tail.parameters.incompatible_mutations: unknown mutation 'Ghost'",
            "mutation.Razor Tail.parameters.disease_predispositions: unknown disease 'Plague'",
            "mutation.Razor Tail.on_death_options: unknown injury 'Paper Cut'",
        ]

    def test_non_list_is_reported(self):
        errors = find_cross_reference_errors([_mutation("X", disease_immunities="Mange")], {"mange"}, set())
        assert errors == ["mutation.X.parameters.disease_immunities: must be a list"]
