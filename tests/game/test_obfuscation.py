"""Tests for src/game/obfuscation.py."""

from src.game.utils.obfuscation import (
    consumption_label,
    health_label,
    mess_output_label,
    messiness_label,
    size_label,
    starvation_label,
    stat_label,
)


def test_stat_label_average():
    assert stat_label(10) == "Average"


def test_stat_label_very_low():
    assert stat_label(0) == "Very Low"
    assert stat_label(2) == "Very Low"


def test_stat_label_low():
    assert stat_label(5) == "Low"
    assert stat_label(7) == "Low"


def test_stat_label_slightly_low():
    assert stat_label(8) == "Slightly Low"
    assert stat_label(9) == "Slightly Low"


def test_stat_label_slightly_high():
    assert stat_label(11) == "Slightly High"
    assert stat_label(12) == "Slightly High"


def test_stat_label_high():
    assert stat_label(13) == "High"
    assert stat_label(15) == "High"


def test_stat_label_very_high():
    assert stat_label(16) == "Very High"
    assert stat_label(1000) == "Very High"


def test_stat_label_none():
    assert stat_label(None) == "Unknown"


def test_health_label_dead_when_zero():
    assert health_label(0) == "Dead"


def test_health_label_healthy_baseline():
    assert health_label(10) == "Healthy"


def test_health_label_critical():
    assert health_label(1) == "Critical"
    assert health_label(2) == "Critical"


def test_health_label_robust():
    assert health_label(12) == "Robust"


def test_messiness_label_spotless():
    assert messiness_label(0) == "Spotless"


def test_messiness_label_mostly_clean():
    assert messiness_label(2) == "Mostly Clean"


def test_messiness_label_messy():
    assert messiness_label(5) == "Messy"


def test_messiness_label_very_messy():
    assert messiness_label(10) == "Very Messy"


def test_messiness_label_disgusting():
    assert messiness_label(20) == "Disgusting"


def test_messiness_label_biohazard_at_the_cap():
    assert messiness_label(24) == "Disgusting"
    assert messiness_label(25) == "Biohazard"
    assert messiness_label(400) == "Biohazard"


def test_starvation_label_well_fed_on_none():
    assert starvation_label(None) == "Well-fed"
    assert starvation_label(0) == "Well-fed"


def test_starvation_label_escalation():
    assert starvation_label(3) == "Peckish"
    assert starvation_label(10) == "Hungry"
    assert starvation_label(20) == "Famished"
    assert starvation_label(40) == "Starving"
    assert starvation_label(100) == "Dying of Hunger"


def test_size_label_ranges():
    assert size_label(1) == "Tiny"
    assert size_label(7) == "Small"
    assert size_label(15) == "Medium"
    assert size_label(25) == "Large"
    assert size_label(45) == "Very Large"
    assert size_label(70) == "Giant"


def test_mess_output_label_ranges():
    assert mess_output_label(0) == "Tidy"
    assert mess_output_label(2) == "Ordinary"
    assert mess_output_label(4) == "Messy"
    assert mess_output_label(7) == "Very Messy"
    assert mess_output_label(20) == "Filthy"


def test_consumption_label_ranges():
    assert consumption_label(0) == "Tiny Appetite"
    assert consumption_label(2) == "Light Eater"
    assert consumption_label(4) == "Average Appetite"
    assert consumption_label(7) == "Big Eater"
    assert consumption_label(20) == "Ravenous"
