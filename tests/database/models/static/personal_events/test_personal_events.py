"""Tests for src/database/models/static/personal_events/ ORM model classes.

These tests verify that each model is importable, has the expected class-level
attributes (tablename, columns, relationships, constraints), and that the
__init__ module re-exports them correctly.  No database I/O is performed.

Import isolation
----------------
The personal_events package shares tablenames with owner_events (both map
``event_actions`` etc.).  Importing via the normal ``src.database.models``
package causes SQLAlchemy to raise ``InvalidRequestError`` because
``owner_events`` is registered first by the package __init__.

We therefore bootstrap the personal_events models using importlib so that
only the minimal required dependencies are loaded and the conflicting
owner_events tables are never registered in the same MetaData instance.

The bootstrap is careful to:
- Only install stubs for packages not yet in sys.modules
- Restore sys.modules to its previous state after loading the target modules
  (so that other tests in the same session can still import src.database.*)
"""

from __future__ import annotations

import importlib.util
import sys
import types

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import RelationshipProperty

# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------


def _load_module_direct(mod_name: str, file_path: str) -> types.ModuleType:
    """Load a single Python source file under a given fully-qualified name."""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _bootstrap() -> dict:
    """
    Load the four personal_events model classes without triggering the
    full src.database.models package initialisation.

    Strategy
    --------
    1. Snapshot the current sys.modules state.
    2. Install lightweight stubs for any parent packages that haven't been
       loaded yet (so Python won't execute their __init__.py files).
    3. Load each required file directly via importlib.
    4. Restore sys.modules for all the stub packages we installed, leaving
       only the personal_events module entries in place (so subsequent
       imports in other test modules work normally).
    """
    pe_pkg = "src.database.models.static.personal_events"

    # If the personal_events modules were already successfully loaded by a
    # previous bootstrap call (e.g., during collection of this very file),
    # just return them.
    if f"{pe_pkg}.event" in sys.modules and f"{pe_pkg}.event_action" in sys.modules:
        return {
            "Event": sys.modules[f"{pe_pkg}.event"].Event,
            "EventAction": sys.modules[f"{pe_pkg}.event_action"].EventAction,
            "EventOption": sys.modules[f"{pe_pkg}.event_option"].EventOption,
            "EventOutcome": sys.modules[f"{pe_pkg}.event_outcome"].EventOutcome,
        }

    # Scaffold packages: parent namespaces whose __init__.py we must prevent
    # from running.  We stub any that are not yet in sys.modules and then
    # remove those stubs after loading so other test modules can import the
    # real src.database.* packages normally.
    scaffold_packages = [
        "src",
        "src.database",
        "src.database.models",
        "src.database.models.enums",
        "src.database.models.static",
        "src.database.models.static.owner_events",
    ]
    # Packages we will fully load — keep them in sys.modules after bootstrap.
    keep_packages = [
        "src.database.models.static.server_events",
        "src.database.models.static.personal_events",
    ]

    # Stub scaffold packages that aren't already in sys.modules.
    stubbed_scaffold_keys: list[str] = []
    for pkg in scaffold_packages + keep_packages:
        if pkg not in sys.modules:
            sys.modules[pkg] = types.ModuleType(pkg)
            if pkg in scaffold_packages:
                stubbed_scaffold_keys.append(pkg)

    try:
        # Expose Base on the stub so ``from ... import Base`` works.
        base_mod = _load_module_direct(
            "src.database.models.base",
            "src/database/models/base.py",
        )
        sys.modules["src.database.models"].Base = base_mod.Base

        # Enums
        _load_module_direct(
            "src.database.models.enums.event_action_type",
            "src/database/models/enums/event_action_type.py",
        )
        _load_module_direct(
            "src.database.models.enums.event_severity",
            "src/database/models/enums/event_severity.py",
        )
        _load_module_direct(
            "src.database.models.enums.event_target_type",
            "src/database/models/enums/event_target_type.py",
        )
        _load_module_direct(
            "src.database.models.enums.rarity",
            "src/database/models/enums/rarity.py",
        )
        _load_module_direct(
            "src.database.models.enums",
            "src/database/models/enums/__init__.py",
        )

        # event_types (TypedDicts referenced by mapped columns)
        _load_module_direct(
            "src.database.models.event_types",
            "src/database/models/event_types.py",
        )

        # server_events — needed because EventAction defines relationships to them
        server_event_mod = _load_module_direct(
            "src.database.models.static.server_events.server_event",
            "src/database/models/static/server_events/server_event.py",
        )
        server_event_option_mod = _load_module_direct(
            "src.database.models.static.server_events.server_event_option",
            "src/database/models/static/server_events/server_event_option.py",
        )
        server_event_outcome_mod = _load_module_direct(
            "src.database.models.static.server_events.server_event_outcome",
            "src/database/models/static/server_events/server_event_outcome.py",
        )
        se_pkg = sys.modules["src.database.models.static.server_events"]
        se_pkg.ServerEvent = server_event_mod.ServerEvent
        se_pkg.ServerEventOption = server_event_option_mod.ServerEventOption
        se_pkg.ServerEventOutcome = server_event_outcome_mod.ServerEventOutcome

        # personal_events (the models under test)
        event_mod = _load_module_direct(
            "src.database.models.static.personal_events.event",
            "src/database/models/static/personal_events/event.py",
        )
        event_option_mod = _load_module_direct(
            "src.database.models.static.personal_events.event_option",
            "src/database/models/static/personal_events/event_option.py",
        )
        event_outcome_mod = _load_module_direct(
            "src.database.models.static.personal_events.event_outcome",
            "src/database/models/static/personal_events/event_outcome.py",
        )
        event_action_mod = _load_module_direct(
            "src.database.models.static.personal_events.event_action",
            "src/database/models/static/personal_events/event_action.py",
        )
        # Load the __init__ so re-export assertions work.
        _load_module_direct(
            "src.database.models.static.personal_events",
            "src/database/models/static/personal_events/__init__.py",
        )

        result = {
            "Event": event_mod.Event,
            "EventAction": event_action_mod.EventAction,
            "EventOption": event_option_mod.EventOption,
            "EventOutcome": event_outcome_mod.EventOutcome,
        }

    finally:
        # Remove the scaffold stubs so other test modules can import the
        # real src.database.* packages normally.  We deliberately leave the
        # personal_events and server_events module entries in sys.modules
        # so the loaded classes remain accessible.
        for key in stubbed_scaffold_keys:
            sys.modules.pop(key, None)

    return result


# Run at module-import time.
_MODELS = _bootstrap()

Event = _MODELS["Event"]
EventAction = _MODELS["EventAction"]
EventOption = _MODELS["EventOption"]
EventOutcome = _MODELS["EventOutcome"]


# ---------------------------------------------------------------------------
# Import / re-export tests
# ---------------------------------------------------------------------------


def test_event_importable():
    """Event class is accessible after isolation bootstrap."""
    assert Event is not None


def test_event_action_importable():
    """EventAction class is accessible after isolation bootstrap."""
    assert EventAction is not None


def test_event_option_importable():
    """EventOption class is accessible after isolation bootstrap."""
    assert EventOption is not None


def test_event_outcome_importable():
    """EventOutcome class is accessible after isolation bootstrap."""
    assert EventOutcome is not None


def test_package_init_exports_all_four():
    """The personal_events __init__ re-exports all four model classes."""
    pkg = sys.modules["src.database.models.static.personal_events"]
    assert pkg.Event is Event
    assert pkg.EventAction is EventAction
    assert pkg.EventOption is EventOption
    assert pkg.EventOutcome is EventOutcome


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


class TestEvent:
    def test_tablename(self):
        assert Event.__tablename__ == "events"

    def test_primary_key_column(self):
        col = Event.__table__.c["id"]
        assert col.primary_key

    def test_name_column_is_unique_and_not_nullable(self):
        col = Event.__table__.c["name"]
        assert not col.nullable
        assert col.unique

    def test_category_column(self):
        col = Event.__table__.c["category"]
        assert not col.nullable

    def test_description_column(self):
        col = Event.__table__.c["description"]
        assert not col.nullable

    def test_flavor_text_column(self):
        col = Event.__table__.c["flavor_text"]
        assert not col.nullable

    def test_severity_column(self):
        col = Event.__table__.c["severity"]
        assert not col.nullable

    def test_rarity_column(self):
        col = Event.__table__.c["rarity"]
        assert not col.nullable

    def test_requires_response_column(self):
        col = Event.__table__.c["requires_response"]
        assert not col.nullable

    def test_response_timeout_column(self):
        col = Event.__table__.c["response_timeout"]
        assert not col.nullable

    def test_min_pooches_column(self):
        col = Event.__table__.c["min_pooches"]
        assert not col.nullable

    def test_min_kennels_column(self):
        col = Event.__table__.c["min_kennels"]
        assert not col.nullable

    def test_min_money_column(self):
        col = Event.__table__.c["min_money"]
        assert not col.nullable

    def test_min_bloodskulls_column(self):
        col = Event.__table__.c["min_bloodskulls"]
        assert not col.nullable

    def test_triggered_only_column(self):
        col = Event.__table__.c["triggered_only"]
        assert not col.nullable

    def test_advanced_options_column(self):
        col = Event.__table__.c["advanced_options"]
        assert not col.nullable

    def test_actions_relationship_exists(self):
        mapper = Event.__mapper__
        assert "actions" in mapper.relationships
        rel = mapper.relationships["actions"]
        assert isinstance(rel, RelationshipProperty)

    def test_options_relationship_exists(self):
        mapper = Event.__mapper__
        assert "options" in mapper.relationships
        rel = mapper.relationships["options"]
        assert isinstance(rel, RelationshipProperty)

    def test_actions_relationship_targets_event_action(self):
        mapper = Event.__mapper__
        rel = mapper.relationships["actions"]
        assert rel.mapper.class_.__name__ == "EventAction"

    def test_options_relationship_targets_event_option(self):
        mapper = Event.__mapper__
        rel = mapper.relationships["options"]
        assert rel.mapper.class_.__name__ == "EventOption"

    def test_actions_cascade(self):
        mapper = Event.__mapper__
        rel = mapper.relationships["actions"]
        assert "delete-orphan" in rel.cascade

    def test_options_cascade(self):
        mapper = Event.__mapper__
        rel = mapper.relationships["options"]
        assert "delete-orphan" in rel.cascade


# ---------------------------------------------------------------------------
# EventAction
# ---------------------------------------------------------------------------


class TestEventAction:
    def test_tablename(self):
        assert EventAction.__tablename__ == "event_actions"

    def test_primary_key_column(self):
        col = EventAction.__table__.c["id"]
        assert col.primary_key

    def test_event_id_column_nullable(self):
        col = EventAction.__table__.c["event_id"]
        assert col.nullable

    def test_option_id_column_nullable(self):
        col = EventAction.__table__.c["option_id"]
        assert col.nullable

    def test_outcome_id_column_nullable(self):
        col = EventAction.__table__.c["outcome_id"]
        assert col.nullable

    def test_server_event_id_column_nullable(self):
        col = EventAction.__table__.c["server_event_id"]
        assert col.nullable

    def test_server_event_option_id_column_nullable(self):
        col = EventAction.__table__.c["server_event_option_id"]
        assert col.nullable

    def test_server_event_outcome_id_column_nullable(self):
        col = EventAction.__table__.c["server_event_outcome_id"]
        assert col.nullable

    def test_action_order_column(self):
        col = EventAction.__table__.c["action_order"]
        assert not col.nullable

    def test_action_type_column(self):
        col = EventAction.__table__.c["action_type"]
        assert not col.nullable

    def test_target_type_column(self):
        col = EventAction.__table__.c["target_type"]
        assert not col.nullable

    def test_parameters_column(self):
        col = EventAction.__table__.c["parameters"]
        assert not col.nullable

    def test_check_constraint_exists(self):
        constraint_names = {c.name for c in EventAction.__table__.constraints if isinstance(c, CheckConstraint)}
        assert "event_actions_exactly_one_parent" in constraint_names

    def test_event_relationship_exists(self):
        assert "event" in EventAction.__mapper__.relationships

    def test_option_relationship_exists(self):
        assert "option" in EventAction.__mapper__.relationships

    def test_outcome_relationship_exists(self):
        assert "outcome" in EventAction.__mapper__.relationships

    def test_server_event_relationship_exists(self):
        assert "server_event" in EventAction.__mapper__.relationships

    def test_server_event_option_relationship_exists(self):
        assert "server_event_option" in EventAction.__mapper__.relationships

    def test_server_event_outcome_relationship_exists(self):
        assert "server_event_outcome" in EventAction.__mapper__.relationships

    def test_event_id_has_foreign_key_to_events(self):
        col = EventAction.__table__.c["event_id"]
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "events.id" in fk_targets

    def test_option_id_has_foreign_key_to_event_options(self):
        col = EventAction.__table__.c["option_id"]
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "event_options.id" in fk_targets

    def test_outcome_id_has_foreign_key_to_event_outcomes(self):
        col = EventAction.__table__.c["outcome_id"]
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "event_outcomes.id" in fk_targets


# ---------------------------------------------------------------------------
# EventOption
# ---------------------------------------------------------------------------


class TestEventOption:
    def test_tablename(self):
        assert EventOption.__tablename__ == "event_options"

    def test_primary_key_column(self):
        col = EventOption.__table__.c["id"]
        assert col.primary_key

    def test_event_id_column_not_nullable(self):
        col = EventOption.__table__.c["event_id"]
        assert not col.nullable

    def test_event_id_has_foreign_key_to_events(self):
        col = EventOption.__table__.c["event_id"]
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "events.id" in fk_targets

    def test_option_order_column(self):
        col = EventOption.__table__.c["option_order"]
        assert not col.nullable

    def test_label_column(self):
        col = EventOption.__table__.c["label"]
        assert not col.nullable

    def test_description_column(self):
        col = EventOption.__table__.c["description"]
        assert not col.nullable

    def test_min_money_column(self):
        col = EventOption.__table__.c["min_money"]
        assert not col.nullable

    def test_min_bloodskulls_column(self):
        col = EventOption.__table__.c["min_bloodskulls"]
        assert not col.nullable

    def test_advanced_options_column(self):
        col = EventOption.__table__.c["advanced_options"]
        assert not col.nullable

    def test_event_relationship_exists(self):
        assert "event" in EventOption.__mapper__.relationships

    def test_actions_relationship_exists(self):
        assert "actions" in EventOption.__mapper__.relationships

    def test_outcomes_relationship_exists(self):
        assert "outcomes" in EventOption.__mapper__.relationships

    def test_event_relationship_targets_event(self):
        rel = EventOption.__mapper__.relationships["event"]
        assert rel.mapper.class_.__name__ == "Event"

    def test_actions_relationship_targets_event_action(self):
        rel = EventOption.__mapper__.relationships["actions"]
        assert rel.mapper.class_.__name__ == "EventAction"

    def test_outcomes_relationship_targets_event_outcome(self):
        rel = EventOption.__mapper__.relationships["outcomes"]
        assert rel.mapper.class_.__name__ == "EventOutcome"

    def test_actions_cascade(self):
        rel = EventOption.__mapper__.relationships["actions"]
        assert "delete-orphan" in rel.cascade

    def test_outcomes_cascade(self):
        rel = EventOption.__mapper__.relationships["outcomes"]
        assert "delete-orphan" in rel.cascade


# ---------------------------------------------------------------------------
# EventOutcome
# ---------------------------------------------------------------------------


class TestEventOutcome:
    def test_tablename(self):
        assert EventOutcome.__tablename__ == "event_outcomes"

    def test_primary_key_column(self):
        col = EventOutcome.__table__.c["id"]
        assert col.primary_key

    def test_option_id_column_not_nullable(self):
        col = EventOutcome.__table__.c["option_id"]
        assert not col.nullable

    def test_option_id_has_foreign_key_to_event_options(self):
        col = EventOutcome.__table__.c["option_id"]
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "event_options.id" in fk_targets

    def test_outcome_order_column(self):
        col = EventOutcome.__table__.c["outcome_order"]
        assert not col.nullable

    def test_label_column(self):
        col = EventOutcome.__table__.c["label"]
        assert not col.nullable

    def test_description_column(self):
        col = EventOutcome.__table__.c["description"]
        assert not col.nullable

    def test_message_column(self):
        col = EventOutcome.__table__.c["message"]
        assert not col.nullable

    def test_chance_column_is_nullable(self):
        col = EventOutcome.__table__.c["chance"]
        assert col.nullable

    def test_advanced_options_column(self):
        col = EventOutcome.__table__.c["advanced_options"]
        assert not col.nullable

    def test_check_constraint_exists(self):
        constraint_names = {c.name for c in EventOutcome.__table__.constraints if isinstance(c, CheckConstraint)}
        assert "event_outcomes_chance_range" in constraint_names

    def test_option_relationship_exists(self):
        assert "option" in EventOutcome.__mapper__.relationships

    def test_actions_relationship_exists(self):
        assert "actions" in EventOutcome.__mapper__.relationships

    def test_option_relationship_targets_event_option(self):
        rel = EventOutcome.__mapper__.relationships["option"]
        assert rel.mapper.class_.__name__ == "EventOption"

    def test_actions_relationship_targets_event_action(self):
        rel = EventOutcome.__mapper__.relationships["actions"]
        assert rel.mapper.class_.__name__ == "EventAction"

    def test_actions_cascade(self):
        rel = EventOutcome.__mapper__.relationships["actions"]
        assert "delete-orphan" in rel.cascade
