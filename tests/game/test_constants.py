"""Tests for src/game/constants.py."""


def test_min_health_for_death_chance_is_positive():
    """
    Test min health for death chance is positive.

    Returns
    -------
    Any
        The result of calling `test_min_health_for_death_chance_is_positive`.
    """

    from src.game.constants import MIN_HEALTH_FOR_DEATH_CHANCE

    assert MIN_HEALTH_FOR_DEATH_CHANCE > 0


def test_pooch_stat_range_is_valid_bounds():
    """
    Test pooch stat range is valid bounds.

    Returns
    -------
    Any
        The result of calling `test_pooch_stat_range_is_valid_bounds`.
    """

    from src.game.constants import POOCH_STAT_RANGE

    low, high = POOCH_STAT_RANGE
    assert low > 0
    assert high >= low


def test_breed_rarity_multipliers_all_positive():
    """
    Test breed rarity multipliers all positive.

    Returns
    -------
    Any
        The result of calling `test_breed_rarity_multipliers_all_positive`.
    """

    from src.game.constants import BREED_RARITY_TO_POOCH_VALUE_MULT

    for rarity, mult in BREED_RARITY_TO_POOCH_VALUE_MULT.items():
        assert mult > 0, f"Rarity '{rarity}' has non-positive multiplier {mult}"


def test_vendor_markup_range_is_valid_bounds():
    """
    Test vendor markup range is valid bounds.

    Returns
    -------
    Any
        The result of calling `test_vendor_markup_range_is_valid_bounds`.
    """

    from src.game.constants import VENDOR_MARKUP_RANGE

    low, high = VENDOR_MARKUP_RANGE
    assert low > 0
    assert high >= low


def test_event_hourly_trigger_chance_is_in_range():
    """
    Test event hourly trigger chance is in range.

    Returns
    -------
    Any
        The result of calling `test_event_hourly_trigger_chance_is_in_range`.
    """

    from src.game.constants import EVENT_HOURLY_TRIGGER_CHANCE

    assert 0.0 <= EVENT_HOURLY_TRIGGER_CHANCE <= 1.0
