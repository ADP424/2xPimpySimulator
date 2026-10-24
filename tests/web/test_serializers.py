"""Tests for src/web/serializers.py — what the web API is allowed to reveal."""

from types import SimpleNamespace

from src.game.models import (
    Pooch,
    PoochDiseaseInfo,
    PoochInjuryInfo,
    PoochMutationInfo,
)
from src.web.serializers import (
    serialize_breed,
    serialize_disease,
    serialize_injury,
    serialize_kennel,
    serialize_mutation,
    serialize_pooch,
)

_SECRET_PARAMETERS = {"sold_by_vendors": False, "strength_add": 3, "fertility_mult": 1.5}


def _catalog(name, **extra):
    """A breed/mutation-like catalog entry."""
    return SimpleNamespace(
        id=hash(name) % 1000,
        name=name,
        alt_name="",
        category="test",
        description="",
        rarity="rare",
        heritability=0.5,
        health_impact="harmful",
        affects_females=True,
        affects_males=True,
        parameters=dict(_SECRET_PARAMETERS),
        min_size=3,
        max_size=5,
        **extra,
    )


def _injury(name):
    """Only the fields the Injury catalog model really has."""
    return SimpleNamespace(
        id=hash(name) % 1000,
        name=name,
        health_impact="harmful",
        severity="minor",
        description="",
        parameters=dict(_SECRET_PARAMETERS),
        treated={},
        visible=True,
        invisible_messages=None,
        reveal_chance=1.0,
    )


def _disease(name):
    """Only the fields the Disease catalog model really has."""
    return SimpleNamespace(
        id=hash(name) % 1000,
        name=name,
        category="infection",
        description="",
        health_impact="harmful",
        contagion_chance=0.1,
        sexually_transmitted=False,
        recovery_chance=0.1,
        treatable=True,
        curable=True,
        immunity_duration=None,
        heritability=0.0,
        seasons=None,
        season_contagion_modifiers=None,
        parameters=dict(_SECRET_PARAMETERS),
        visible=True,
        invisible_messages=None,
        reveal_chance=1.0,
    )


def _make_pooch(**overrides) -> Pooch:
    defaults = dict(
        id=1,
        name="Rex",
        age=3,
        sex="male",
        base_health=10,
        health_loss_age=0,
        strength=13,
        cuteness=10,
        fluffiness=10,
        intelligence=10,
        dexterity=10,
        fertility=10,
        aggressiveness=10,
        constitution=10,
        breeding_cooldown=4,
        alive=True,
        virgin=True,
        vet_checked=False,
        owner_discord_id=42,
        vendor_id=None,
        created_at=None,
        size=10,
        health=8,
        mood=None,
        owner=SimpleNamespace(discord_id=42, discord_name="Liam", dollars=9999, bloodskulls=7, bones=3),
        vendor=None,
        breeds=[],
        mutations=[
            PoochMutationInfo(mutation=_catalog("Albinism"), displayed_symptom=None, visible=True),
            PoochMutationInfo(mutation=_catalog("Secret Gene"), displayed_symptom="odd eyes", visible=False),
        ],
        injuries=[
            PoochInjuryInfo(injury=_injury("Sprain"), displayed_symptom=None, visible=True),
            PoochInjuryInfo(injury=_injury("Hidden Fracture"), displayed_symptom="a limp", visible=False),
        ],
        diseases=[
            PoochDiseaseInfo(disease=_disease("Flu"), displayed_symptom=None, visible=True, treated=True),
            PoochDiseaseInfo(
                disease=_disease("Secret Plague"), displayed_symptom="a cough", visible=False, treated=False
            ),
        ],
    )
    defaults.update(overrides)
    return Pooch(**defaults)


class TestSerializePooch:
    def test_hides_exact_health_and_cooldown(self):
        data = serialize_pooch(_make_pooch())
        for key in ("health", "base_health", "health_loss_age", "breeding_cooldown"):
            assert key not in data
        assert data["breeding_status"] == "heating_up"
        assert data["can_breed"] is False
        assert data["status"] == "healthy"

    def test_hides_raw_stats(self):
        data = serialize_pooch(_make_pooch())
        for stat in ("strength", "cuteness", "fertility", "constitution", "size"):
            assert stat not in data

    def test_owner_has_identity_only(self):
        assert serialize_pooch(_make_pooch())["owner"] == {"discord_id": 42, "discord_name": "Liam"}

    def test_vendor_summary(self):
        data = serialize_pooch(_make_pooch(owner=None, vendor=SimpleNamespace(id=5, name="Bob", price_markup=1.2)))
        assert data["vendor"] == {"id": 5, "name": "Bob"}
        assert "owner" not in data

    def test_hidden_conditions_only_as_symptoms(self):
        data = serialize_pooch(_make_pooch())
        assert [m["name"] for m in data["mutations"]] == ["Albinism"]
        assert [i["name"] for i in data["injuries"]] == ["Sprain"]
        assert [d["name"] for d in data["diseases"]] == ["Flu"]
        assert data["diseases"][0]["treated"] is True
        assert data["mutation_symptoms"] == ["odd eyes"]
        assert data["injury_symptoms"] == ["a limp"]
        assert data["disease_symptoms"] == ["a cough"]
        flat = repr(data)
        for secret in ("Secret Gene", "Hidden Fracture", "Secret Plague"):
            assert secret not in flat

    def test_without_relations_has_no_conditions(self):
        data = serialize_pooch(_make_pooch(), include_relations=False)
        assert "injuries" not in data
        assert "owner" not in data


class TestCatalogParameters:
    def test_breed_parameters_public_keys_only(self):
        assert serialize_breed(_catalog("Lab"))["parameters"] == {"sold_by_vendors": False}

    def test_mutation_parameters_public_keys_only(self):
        assert serialize_mutation(_catalog("Albinism"))["parameters"] == {"sold_by_vendors": False}

    def test_missing_parameters(self):
        breed = _catalog("Lab")
        breed.parameters = None
        assert serialize_breed(breed)["parameters"] == {}

    def test_breed_stat_effects_and_size(self):
        data = serialize_breed(_catalog("Lab"))
        assert [(e["label"], e["text"]) for e in data["stat_effects"]] == [("Strength", "+3"), ("Fertility", "×1.5")]
        assert (data["min_size"], data["max_size"]) == (3, 5)

    def test_mutation_stat_effects(self):
        data = serialize_mutation(_catalog("Albinism"))
        assert [(e["label"], e["text"]) for e in data["stat_effects"]] == [("Strength", "+3"), ("Fertility", "×1.5")]

    def test_missing_parameters_have_no_stat_effects(self):
        breed = _catalog("Lab")
        breed.parameters = None
        assert serialize_breed(breed)["stat_effects"] == []


class TestEncyclopedia:
    def test_injury_matches_bot_fields_only(self):
        injury = _injury("Sprain")
        injury.parameters = {"persistence": 4, "strength_add": -2}
        injury.treated = {"description": "Heals faster", "health_impact": "neutral", "dexterity_add": 1}
        injury.invisible_messages = ["a limp"]
        injury.reveal_chance = 0.3

        data = serialize_injury(injury)

        assert data["persistence"] == 4
        assert data["treated"] == {"description": "Heals faster", "health_impact": "neutral"}
        for hidden in ("parameters", "reveal_chance", "invisible_messages", "visible"):
            assert hidden not in data
        assert "strength_add" not in repr(data) and "dexterity_add" not in repr(data)

    def test_injury_without_treatment(self):
        assert serialize_injury(_injury("Scratch"))["treated"] is None

    def test_disease_matches_bot_fields_only(self):
        disease = _disease("Flu")
        disease.invisible_messages = ["a cough"]
        disease.reveal_chance = 0.2

        data = serialize_disease(disease)

        assert data["contagion_chance"] == 0.1
        assert data["seasons"] == []
        for hidden in ("parameters", "reveal_chance", "invisible_messages", "visible", "season_contagion_modifiers"):
            assert hidden not in data


class TestSerializeKennel:
    def test_includes_messiness(self):
        kennel = SimpleNamespace(id=1, owner_discord_id=42, name="Barn", pooch_limit=5, messiness=12)
        assert serialize_kennel(kennel)["messiness"] == 12
