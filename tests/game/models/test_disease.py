"""Tests for src/game/models/disease.py."""

from unittest.mock import MagicMock

import pytest

from src.game.models.disease import Disease, to_disease

# ---------------------------------------------------------------------------
# Disease dataclass creation
# ---------------------------------------------------------------------------


class TestDiseaseCreation:
    def test_basic_creation(self):
        d = Disease(
            id=1,
            name="Kennel Cough",
            category="Viral",
            description="Respiratory infection.",
            health_impact="harmful",
            contagion_chance=0.5,
            sexually_transmitted=False,
            recovery_chance=0.3,
            treatable=True,
            curable=True,
            immunity_duration=30,
            heritability=0.1,
            seasons=["winter"],
            season_contagion_modifiers={"winter": 1.5},
        )
        assert d.id == 1
        assert d.name == "Kennel Cough"
        assert d.category == "Viral"
        assert d.description == "Respiratory infection."
        assert d.health_impact == "harmful"
        assert d.contagion_chance == 0.5
        assert d.sexually_transmitted is False
        assert d.recovery_chance == 0.3
        assert d.treatable is True
        assert d.curable is True
        assert d.immunity_duration == 30
        assert d.heritability == 0.1
        assert d.seasons == ["winter"]
        assert d.season_contagion_modifiers == {"winter": 1.5}

    def test_defaults_parameters_empty_dict(self):
        d = Disease(
            id=1,
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert d.parameters == {}

    def test_defaults_visible_true(self):
        d = Disease(
            id=1,
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert d.visible is True

    def test_defaults_invisible_messages_none(self):
        d = Disease(
            id=1,
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert d.invisible_messages is None

    def test_defaults_reveal_chance_one(self):
        d = Disease(
            id=1,
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert d.reveal_chance == 1.0

    def test_frozen(self):
        d = Disease(
            id=1,
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        with pytest.raises(AttributeError):
            d.name = "Changed"  # type: ignore[misc]

    def test_equality(self):
        args = dict(
            id=1,
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert Disease(**args) == Disease(**args)

    def test_inequality_different_id(self):
        args = dict(
            name="Test",
            category="test",
            description="",
            health_impact="neutral",
            contagion_chance=0.0,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert Disease(id=1, **args) != Disease(id=2, **args)

    def test_std_disease(self):
        d = Disease(
            id=2,
            name="Canine STD",
            category="Sexual",
            description="Transmitted during breeding.",
            health_impact="harmful",
            contagion_chance=0.8,
            sexually_transmitted=True,
            recovery_chance=0.05,
            treatable=True,
            curable=True,
            immunity_duration=60,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
        )
        assert d.sexually_transmitted is True
        assert d.contagion_chance == 0.8

    def test_invisible_disease(self):
        d = Disease(
            id=3,
            name="Silent Infection",
            category="Viral",
            description="Hard to detect.",
            health_impact="harmful",
            contagion_chance=0.3,
            sexually_transmitted=False,
            recovery_chance=0.2,
            treatable=True,
            curable=True,
            immunity_duration=None,
            heritability=0.0,
            seasons=None,
            season_contagion_modifiers=None,
            visible=False,
            invisible_messages=["Your pooch seems fine...", "Nothing unusual."],
            reveal_chance=0.5,
        )
        assert d.visible is False
        assert len(d.invisible_messages) == 2
        assert d.reveal_chance == 0.5

    def test_with_parameters(self):
        params = {"base_health_add": -3, "constitution_mult": 0.8, "death_message": "died of plague"}
        d = Disease(
            id=4,
            name="Plague",
            category="Bacterial",
            description="Deadly plague.",
            health_impact="severe",
            contagion_chance=0.9,
            sexually_transmitted=False,
            recovery_chance=0.0,
            treatable=False,
            curable=False,
            immunity_duration=None,
            heritability=0.0,
            seasons=["summer"],
            season_contagion_modifiers={"summer": 2.0},
            parameters=params,
        )
        assert d.parameters["base_health_add"] == -3
        assert d.parameters["death_message"] == "died of plague"


# ---------------------------------------------------------------------------
# to_disease
# ---------------------------------------------------------------------------


class TestToDisease:
    async def test_converts_orm_to_disease(self):
        orm = MagicMock()
        orm.id = 10
        orm.name = "Distemper"
        orm.category = "Viral"
        orm.description = "Dangerous virus."
        orm.health_impact = "severe"
        orm.contagion_chance = 0.7
        orm.sexually_transmitted = False
        orm.recovery_chance = 0.1
        orm.treatable = True
        orm.curable = True
        orm.immunity_duration = 60
        orm.heritability = 0.2
        orm.seasons = ["winter", "spring"]
        orm.season_contagion_modifiers = {"winter": 1.5}
        orm.parameters = {"base_health_add": -5}
        orm.visible = True
        orm.invisible_messages = None
        orm.reveal_chance = 1.0

        result = await to_disease(orm)
        assert isinstance(result, Disease)
        assert result.id == 10
        assert result.name == "Distemper"
        assert result.category == "Viral"
        assert result.health_impact == "severe"
        assert result.contagion_chance == 0.7
        assert result.sexually_transmitted is False
        assert result.recovery_chance == 0.1
        assert result.treatable is True
        assert result.curable is True
        assert result.immunity_duration == 60
        assert result.heritability == 0.2
        assert result.seasons == ["winter", "spring"]
        assert result.season_contagion_modifiers == {"winter": 1.5}
        assert result.parameters == {"base_health_add": -5}

    async def test_converts_none_parameters_to_empty_dict(self):
        orm = MagicMock()
        orm.id = 1
        orm.name = "Test"
        orm.category = "test"
        orm.description = ""
        orm.health_impact = "neutral"
        orm.contagion_chance = 0.0
        orm.sexually_transmitted = False
        orm.recovery_chance = 0.0
        orm.treatable = True
        orm.curable = True
        orm.immunity_duration = None
        orm.heritability = 0.0
        orm.seasons = None
        orm.season_contagion_modifiers = None
        orm.parameters = None
        orm.visible = True
        orm.invisible_messages = None
        orm.reveal_chance = 1.0

        result = await to_disease(orm)
        assert result.parameters == {}

    async def test_preserves_invisible_fields(self):
        orm = MagicMock()
        orm.id = 5
        orm.name = "Hidden Bug"
        orm.category = "Parasitic"
        orm.description = "Sneaky."
        orm.health_impact = "harmful"
        orm.contagion_chance = 0.1
        orm.sexually_transmitted = False
        orm.recovery_chance = 0.3
        orm.treatable = True
        orm.curable = True
        orm.immunity_duration = None
        orm.heritability = 0.0
        orm.seasons = None
        orm.season_contagion_modifiers = None
        orm.parameters = {}
        orm.visible = False
        orm.invisible_messages = ["All clear..."]
        orm.reveal_chance = 0.3

        result = await to_disease(orm)
        assert result.visible is False
        assert result.invisible_messages == ["All clear..."]
        assert result.reveal_chance == 0.3
