"""
Core gameplay constants.
"""

# Pooch Lifecycle
MIN_HEALTH_FOR_DEATH_CHANCE = 5
DEATH_CHANCE_PER_HEALTH_UNDER_MIN = 0.2
POOCH_BASE_HEALTH_RANGE = (8, 12)

# Vendor Creation
NUM_VENDORS_PER_SERVER = 3
VENDOR_POOCH_STOCK_COUNT_RANGE = (2, 5)

# Vendor Pooch Creation
VENDOR_POOCH_AGE_RANGE = (0, 5)
NUM_BREEDS_PER_VENDOR_POOCH_RANGE = (1, 3)
NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE = (0, 2)

# Vendor Pooch Pricing
VENDOR_MARKUP_RANGE = (1.15, 1.25)
BASE_POOCH_DOLLAR_VALUE = 75
POOCH_DOLLAR_VALUE_LOSS_BY_AGE = 5
POOCH_DOLLAR_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE = 5
BREED_RARITY_TO_DOLLAR_VALUE_MULT = {
    "common": 0.5,
    "uncommon": 1.0,
    "novel": 1.5,
    "rare": 2.0,
    "unprecedented": 2.5,
    "remarkable": 3.0,
    "extraordinary": 4.0,
    "unique": 5.0,
}
VENDOR_DESIRED_MUTATION_MULT = 2
