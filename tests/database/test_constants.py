"""Tests for src/database/constants.py."""


def test_pooch_base_health_is_positive():
    from src.database.constants import POOCH_BASE_HEALTH

    assert POOCH_BASE_HEALTH > 0


def test_pooch_stat_default_is_positive():
    from src.database.constants import POOCH_STAT_DEFAULT

    assert POOCH_STAT_DEFAULT > 0


def test_kennel_pooch_limit_is_positive():
    from src.database.constants import KENNEL_POOCH_LIMIT

    assert KENNEL_POOCH_LIMIT > 0


def test_vendor_price_markup_is_positive():
    from src.database.constants import VENDOR_PRICE_MARKUP

    assert VENDOR_PRICE_MARKUP > 0


def test_random_seed_size_limit_is_positive():
    from src.database.constants import RANDOM_SEED_SIZE_LIMIT

    assert RANDOM_SEED_SIZE_LIMIT > 0
