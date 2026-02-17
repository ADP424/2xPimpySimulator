"""
Database-layer constants.

These define default weights, rarity distributions, and generation ranges.
They should not encode logic, only values.
"""

# Pooch Defaults
POOCH_BASE_HEALTH = 10
POOCH_HEALTH_LOSS_AGE = 0
POOCH_BREEDING_COOLDOWN = 2
POOCH_FETAL_AGE = -1

# Owner / Kennel Defaults
KENNEL_POOCH_LIMIT = 10

# Vendor Defaults
VENDOR_PRICE_MARKUP = 1.0

# Database RNG
RANDOM_SEED_SIZE_LIMIT = 2**16
