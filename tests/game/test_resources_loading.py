"""Tests that validate every JSONC resource file parses cleanly.

These tests don't touch the database — they just exercise the pure
validators over the real on-disk resources. If any new resource file has
a typo or schema error, this test fails loudly so you catch it before
the loader runs at startup.
"""

from pathlib import Path

import pytest

from src.database.load.load_resources.breeds import validate_breeds_json
from src.database.load.load_resources.diseases import validate_diseases_json
from src.database.load.load_resources.injuries import load_injuries  # noqa: F401
from src.database.load.load_resources.items import validate_items_json
from src.database.load.load_resources.mutations import validate_mutations_json
from src.database.load.load_resources.utils import load_categorized_resource_objects


@pytest.fixture
def resources_root() -> Path:
    return Path(__file__).resolve().parents[2] / "resources"


class TestBreedResources:
    def test_breeds_parse_and_validate(self, resources_root):
        d = load_categorized_resource_objects(resources_root / "breeds", "breed")
        assert sum(len(v) for v in d.values()) > 0
        validate_breeds_json(d)


class TestMutationResources:
    def test_mutations_parse_and_validate(self, resources_root):
        d = load_categorized_resource_objects(resources_root / "mutations", "mutation")
        assert sum(len(v) for v in d.values()) > 0
        validate_mutations_json(d)

    def test_razor_tail_mutation_uses_injure_effect(self, resources_root):
        d = load_categorized_resource_objects(resources_root / "mutations", "mutation")
        # The "Limb Deformities" category (or similar slug) contains Razor Tail.
        found = False
        for category_items in d.values():
            if "Razor Tail" in category_items:
                found = True
                params = category_items["Razor Tail"]["parameters"]
                triggers = params["on_death_triggers"]
                assert triggers[0]["on_death"] == "injure"
                assert "Minor Scratch" in triggers[0]["on_death_options"]
        assert found, "Razor Tail mutation should exist"


class TestDiseaseResources:
    def test_disease_files_parse_and_validate(self, resources_root):
        root = resources_root / "diseases"
        if not root.exists():
            pytest.skip("No disease resources directory.")
        d = load_categorized_resource_objects(root, "disease")
        assert sum(len(v) for v in d.values()) >= 5, "expected at least 5 disease resources"
        validate_diseases_json(d)

    def test_disease_covers_required_varieties(self, resources_root):
        """The spec requires 5 diseases covering: sexually transmitted, heritable,
        seasonal bias, visible/ambiguous symptoms, and benefits from treatment."""
        root = resources_root / "diseases"
        d = load_categorized_resource_objects(root, "disease")
        all_diseases = []
        for category_items in d.values():
            all_diseases.extend(category_items.values())

        assert any(disease.get("sexually_transmitted") for disease in all_diseases), "Need at least one STD"
        assert any(
            float(disease.get("heritability", 0)) > 0 for disease in all_diseases
        ), "Need at least one inheritable disease"
        assert any(
            disease.get("seasons") or disease.get("season_contagion_modifiers") for disease in all_diseases
        ), "Need at least one disease with seasonal bias"
        assert any(
            disease.get("invisible_messages") for disease in all_diseases
        ), "Need at least one disease with ambiguous symptoms"
        assert any(disease.get("treatable") for disease in all_diseases), "Need at least one treatable disease"


class TestItemResources:
    def test_item_files_parse_and_validate(self, resources_root):
        root = resources_root / "items"
        if not root.exists():
            pytest.skip("No items directory.")
        d = load_categorized_resource_objects(root, "item")
        validate_items_json(d)

    def test_cleaning_products_present(self, resources_root):
        root = resources_root / "items"
        d = load_categorized_resource_objects(root, "item")
        cleaning_items = {}
        food_items = {}
        for category, items in d.items():
            key = str(category).lower().replace(" ", "_")
            if key == "cleaning":
                cleaning_items.update(items)
            elif key == "food":
                food_items.update(items)
        assert "Soap" in cleaning_items
        assert "Bleach" in cleaning_items
        assert "Trash Bags" in cleaning_items
        assert len(food_items) >= 3


class TestInjuryResources:
    def test_cannibalism_guilt_injury_exists(self, resources_root):
        root = resources_root / "injuries"
        d = load_categorized_resource_objects(root, "injury")
        all_injuries = {}
        for items in d.values():
            all_injuries.update(items)
        assert "Cannibalism Guilt" in all_injuries
