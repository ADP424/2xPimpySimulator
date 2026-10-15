"""Tests for src/game/pronouns.py."""

from types import SimpleNamespace

from src.game.utils.pronouns import substitute_placeholders


def _p(name="Fido", sex="male"):
    return SimpleNamespace(name=name, sex=sex)


def test_basic_name_substitution():
    out = substitute_placeholders("[pooch] barks", {"pooch": _p("Rex")})
    assert out == "Rex barks"


def test_name_style_placeholder():
    out = substitute_placeholders("[pooch_name] is here", {"pooch": _p("Rex")})
    assert out == "Rex is here"


def test_pronoun_male():
    out = substitute_placeholders(
        "[pooch] wagged [pooch_his] tail because [pooch_he] was happy.",
        {"pooch": _p("Rex", "male")},
    )
    assert out == "Rex wagged his tail because he was happy."


def test_pronoun_female():
    out = substitute_placeholders(
        "[pooch] wagged [pooch_his] tail because [pooch_he] was happy.",
        {"pooch": _p("Luna", "female")},
    )
    assert out == "Luna wagged her tail because she was happy."


def test_pronoun_unknown_sex_falls_back_to_they():
    out = substitute_placeholders(
        "[pooch] wagged [pooch_his] tail because [pooch_he] was happy.",
        {"pooch": _p("Mystery", sex=None)},
    )
    assert out == "Mystery wagged their tail because they was happy."


def test_she_placeholder_resolves_correctly_on_male():
    # "[pooch_she]" means "whatever subjective pronoun fits" — on a male, "he"
    out = substitute_placeholders("[pooch_she] runs", {"pooch": _p("Rex", "male")})
    assert out == "he runs"


def test_capitalization_title_case():
    out = substitute_placeholders("[pooch_He] ran", {"pooch": _p("Rex", "male")})
    assert out == "He ran"


def test_capitalization_all_upper():
    out = substitute_placeholders("[pooch_HE] RAN", {"pooch": _p("Rex", "male")})
    assert out == "HE RAN"


def test_capitalization_female_title():
    out = substitute_placeholders("[pooch_He] ran", {"pooch": _p("Luna", "female")})
    assert out == "She ran"


def test_victim_role():
    out = substitute_placeholders(
        "[victim] was caught in [pooch]'s blast.",
        {"pooch": _p("Rex", "male"), "victim": _p("Luna", "female")},
    )
    assert out == "Luna was caught in Rex's blast."


def test_reflexive_pronoun_male():
    out = substitute_placeholders("[pooch] licked [pooch_himself]", {"pooch": _p("Rex", "male")})
    assert out == "Rex licked himself"


def test_reflexive_pronoun_female():
    out = substitute_placeholders("[pooch_Herself] be damned", {"pooch": _p("Luna", "female")})
    assert out == "Herself be damned"


def test_reflexive_unknown_sex():
    out = substitute_placeholders("[pooch_himself]", {"pooch": _p("Unknown", sex=None)})
    assert out == "themselves"


def test_unknown_role_left_alone():
    out = substitute_placeholders("[bogus_he] wins", {"pooch": _p("Rex", "male")})
    assert out == "[bogus_he] wins"


def test_empty_template():
    assert substitute_placeholders("", {"pooch": _p()}) == ""


def test_template_without_placeholders():
    assert substitute_placeholders("Just text.", {"pooch": _p()}) == "Just text."


def test_none_refs_safe():
    assert substitute_placeholders("[pooch] barks", None) == "[pooch] barks"


def test_missing_role_in_refs_leaves_placeholder():
    out = substitute_placeholders("[victim] was hit by [pooch]", {"pooch": _p("Rex", "male")})
    assert "Rex" in out
    assert "[victim]" in out


def test_multiple_roles_and_pronouns():
    out = substitute_placeholders(
        "[pooch] gave [victim_her] a treat, then [pooch_he] wagged [pooch_his] tail.",
        {"pooch": _p("Rex", "male"), "victim": _p("Luna", "female")},
    )
    assert out == "Rex gave her a treat, then he wagged his tail."
