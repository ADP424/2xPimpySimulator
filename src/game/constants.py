from __future__ import annotations

# Pooch Lifecycle
MIN_HEALTH_FOR_DEATH_CHANCE = 5
POOCH_HEALTH_LOSS_STARTING_AGE = 5
POOCH_OLD_AGE = 12  # Status shows "old" from this age
POOCH_SICK_HEALTH = 5  # Status shows "sick" at or below this effective health
# Hourly death chance per health point below MIN_HEALTH_FOR_DEATH_CHANCE.
# At health=0 (deficit=5): 5 * 0.008 = 4% per hour → ~64% over 24 hours.
# At health=3 (deficit=2): 2 * 0.008 = 1.6% per hour → ~32% over 24 hours.
HOURLY_DEATH_CHANCE_PER_HEALTH_UNDER_MIN = 0.008
POOCH_STAT_RANGE = (8, 12)
POOCH_BREEDING_COOLDOWN = 10
BREEDING_COOLDOWN_HOURLY_FERTILITY_DIVISOR = 25
BREEDING_COOLDOWN_HEATING_UP_THRESHOLD = 5
INJURY_PERSISTENCE_HOURLY_CONSTITUTION_DIVISOR = 50

# Strays also roll for disease contraction hourly. Their "dirty outdoors"
# environmental mess modifier — equivalent to a medium-dirty kennel.
STRAY_ENVIRONMENTAL_MESSINESS = 10
# Kennel mess never grows past this, whatever the kennel's size (it affects every pooch inside evenly).
KENNEL_MAX_MESSINESS = 25
# Pregnancy timer range (hours) set when a pooch becomes pregnant.
PREGNANCY_TIMER_HOURS_RANGE = (15, 20)
# Per-hour miscarriage base chance for a healthy young pooch (age≤5, constitution=10,
# starvation=0). Over a 15–20 hour pregnancy this gives ~8% cumulative miscarriage
# chance at baseline; higher for old/weak/starving mothers.
MISCARRIAGE_HOURLY_BASE_CHANCE = 0.005
# Per-pup stillbirth base chance at moment of birth.
STILLBIRTH_BASE_CHANCE = 0.01

# Hourly aggression fight mechanics
HOURLY_FIGHT_BASE_CHANCE = 0.0005  # 0.05% base per pooch per hour
HOURLY_FIGHT_AGGRESSION_SCALE = 0.0002  # per aggressiveness point over 10
HOURLY_FIGHT_STARVATION_SCALE = 0.0005  # per point of starvation
HOURLY_FIGHT_HEALTH_PENALTY = 0.05  # low health → fewer fights

# Food / starvation
POOCH_BASE_CONSUMPTION = 1
POOCH_CONSUMPTION_PER_SIZE_UNIT = 0.1  # consumption scales with size

# Mess output per pooch per hour
POOCH_BASE_MESS_OUTPUT = 2
POOCH_MESS_OUTPUT_PER_SIZE_UNIT = 0.15  # mess scales with size
STARVATION_DECAY_PER_FED_HOUR = 1
STARVATION_PENALTY_PER_STAT = 0.02  # multiplicative stat penalty per starvation unit

# Cannibalism: each hour a starving pooch may eat a kennel-mate (base + multiplier x starvation)
CANNIBALISM_HOURLY_BASE_CHANCE = 0.0002
CANNIBALISM_STARVATION_MULTIPLIER = 0.0005
CANNIBALISM_GUILT_INJURY = "Cannibalism Guilt"

# Chance, per item fed, that each pooch in the kennel gains a food's permanent stat bonus (e.g. strength_add)
FOOD_STAT_BONUS_CHANCE = 0.05

# Body-part drop rates on sacrifice (per part, base chance × size factor)
# These are used by the rituals module. Each tuple is (min, max, per_size_divisor).
BODY_PART_DROP_RATES = {
    "bone": {"base_min": 2, "base_max": 6, "chance": 1.0},
    "teeth": {"base_min": 2, "base_max": 6, "chance": 1.0},
    "eye": {"base_min": 1, "base_max": 2, "chance": 0.45},
    "brain": {"base_min": 1, "base_max": 1, "chance": 0.22},
    "heart": {"base_min": 1, "base_max": 1, "chance": 0.22},
    "tail": {"base_min": 1, "base_max": 1, "chance": 0.2},
}

# Rejuvenation penalties per count (cumulative multiplicative)
REJUVENATION_FERTILITY_MULT = 0.95
REJUVENATION_CONSTITUTION_MULT = 0.95

# Rituals — costs in bloodskulls and body parts.
CLONE_RITUAL_BLOODSKULLS_MIN = 100
CLONE_RITUAL_BLOODSKULLS_VALUE_MULT = 5
CLONE_RITUAL_BRAIN_COST = 1
CLONE_RITUAL_HEART_COST = 1

REJUVENATION_RITUAL_BLOODSKULLS = 150
REJUVENATION_RITUAL_HEART_COST = 1

GENDER_CHANGE_RITUAL_BLOODSKULLS = 75
GENDER_CHANGE_RITUAL_EYE_COST = 1

IMMORTALITY_RITUAL_BLOODSKULLS = 1000
IMMORTALITY_RITUAL_HEART_COST = 1
IMMORTALITY_RITUAL_BRAIN_COST = 1
IMMORTALITY_RITUAL_EYE_COST = 2
IMMORTALITY_RITUAL_TAIL_COST = 1

# All heritable pooch stats (all use POOCH_STAT_RANGE)
# The size range is determined by breeds, so that's why it's not included here
# Injury severities, least to most severe
INJURY_SEVERITIES = ("trivial", "minor", "moderate", "major", "critical", "remarkable", "catastrophic")

POOCH_STATS = [
    "strength",
    "cuteness",
    "fluffiness",
    "intelligence",
    "dexterity",
    "fertility",
    "aggressiveness",
    "constitution",
]

# Breed Inheritance
SHARED_BREED_WEIGHT_BONUS = 1.5  # multiplier applied to a breed weight when both parents share that breed
BREED_NOISE_RANGE = (0.75, 1.5)  # random noise multiplier applied to each breed weight during inheritance

# Baby
POOCH_FETAL_AGE = -1
TWINS_CHANCE = 0.25
TRIPLETS_CHANCE = 0.05
NUM_INCEST_MUTATION_ROLLS = 3

# Vendor Creation
NUM_VENDORS_PER_SERVER = 3
VENDOR_POOCH_STOCK_COUNT_RANGE = (3, 5)

# Vendor Pooch Creation
VENDOR_POOCH_AGE_RANGE = (0, 5)
NUM_BREEDS_PER_VENDOR_POOCH_RANGE = (1, 3)
NUM_MUTATIONS_PER_VENDOR_POOCH_RANGE = (0, 2)

# Pooch Breed Value
BREED_RARITY_TO_POOCH_VALUE_MULT = {
    "common": 0.5,
    "uncommon": 1.0,
    "novel": 1.5,
    "rare": 2.0,
    "unprecedented": 2.5,
    "remarkable": 3.0,
    "extraordinary": 4.0,
    "unique": 5.0,
}

# Vendor Pooch Pricing
VENDOR_MARKUP_RANGE = (1.15, 1.5)
BASE_POOCH_DOLLAR_VALUE = 75
POOCH_DOLLAR_VALUE_LOSS_BY_AGE = 5
POOCH_DOLLAR_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE = 5
VENDOR_DESIRED_MUTATION_MULT = 2

# Vendor Pure-Breed Pricing
# A pooch whose dominant breed makes up <= this fraction of its total weight gets no bonus (1x).
# At 100% it gets VENDOR_PURE_BREED_MAX_MULT. The range scales linearly between the two.
VENDOR_PURE_BREED_THRESHOLD = 0.5
VENDOR_PURE_BREED_MAX_MULT = 2.0

# Sacrifice Value
BASE_POOCH_BLOODSKULL_VALUE = 8
POOCH_BLOODSKULL_VIRGINITY_MULT = 2
POOCH_BLOODSKULL_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE = 1

# Pooch Summoning
BASE_POOCH_SUMMON_PRICE = 20
BLOODSKULL_PRICE_PER_POOCH_SUMMON_ROLL = 1
NUM_BREEDS_PER_SUMMON_POOCH_RANGE = (2, 3)

# Owner Event System Constants
EVENT_HOURLY_TRIGGER_CHANCE = 0.15
EVENT_MAX_ACTIVE_PER_OWNER = 5
EVENT_DEFAULT_TIMEOUT_HOURS = 24

# A new player's first kennel starts with this much food
STARTING_KENNEL_FOOD = 150

# Kennel Purchasing / Upgrades
KENNEL_BASE_PRICE = 250
MAX_KENNELS = 5
KENNEL_UPGRADE_BASE_CAPACITY = 10
KENNEL_UPGRADE_CAPACITY_PER_UPGRADE = 5
KENNEL_MAX_POOCH_LIMIT = 25
KENNEL_UPGRADE_PRICE_PER_5 = 200  # cost per 5-pooch increment above 5

# Church Begging
BEG_DOLLARS_RANGE = (10, 25)
BEG_MAX_DOLLARS = 50

# Strays
PARK_STRAY_CATCH_DIVISOR = 5
STRAY_EVENT_TRIGGER_CHANCE = 0.5

# Fight Mechanics
FIGHT_ROUNDS = 3
FIGHT_ATTACK_STRENGTH_WEIGHT = 0.2
FIGHT_ATTACK_SIZE_STENGTH_WEIGHT = 0.1
FIGHT_ATTACK_DEXTERITY_WEIGHT = 0.1
FIGHT_ATTACK_AGGRESSIVENESS_WEIGHT = 0.2
FIGHT_DEFENSE_STRENGTH_WEIGHT = 0.2
FIGHT_DEFENSE_DEXTERITY_WEIGHT = 0.1
FIGHT_DEFENSE_CONSTITUTION_WEIGHT = 0.2
FIGHT_RANDOM_MULTIPLIER_RANGE = (0.5, 1.5)
FIGHT_DEFENDER_STRENGTH_BONUS = 0

# Per-round strength loss due to fatigue.
# Effective loss = FIGHT_STRENGTH_LOSS_PER_ROUND / (1 + constitution * FIGHT_CONSTITUTION_FATIGUE_REDUCTION)
# At constitution=10: loss = 2 / (1 + 10*0.05) = 2 / 1.5 ≈ 1.33 → rounds to 1
# At constitution=20: loss = 2 / (1 + 20*0.05) = 2 / 2.0 = 1 → rounds to 1
# At constitution=1:  loss = 2 / (1 + 1*0.05)  = 2 / 1.05 ≈ 1.9 → rounds to 2
FIGHT_STRENGTH_LOSS_PER_ROUND = 2
FIGHT_CONSTITUTION_FATIGUE_REDUCTION = 0.05

# Damage thresholds for fight injury selection
FIGHT_SEVERE_BITE_DAMAGE_THRESHOLD = 8
FIGHT_MODERATE_BITE_DAMAGE_THRESHOLD = 4

# Probability of a bite injury vs scratch injury per fight round
FIGHT_INJURY_BITE_CHANCE = 0.6

# Vet treatment costs: cost = VET_TREATMENT_BASE_COST + VET_TREATMENT_SEVERITY_COST_PER_LEVEL * severity_level
VET_TREATMENT_BASE_COST = 5
VET_TREATMENT_SEVERITY_COST_PER_LEVEL = 3

# How much persistence is reduced per vet treatment
VET_TREATMENT_PERSISTENCE_REDUCTION = 10

# Vet diagnosis costs (flat fee per procedure)
VET_DIAGNOSE_INJURIES_COST = 13
VET_DIAGNOSE_MUTATIONS_COST = 25

# Neuter cost (applied at vet clinic)
NEUTER_COST = 25

# Other
MAX_NAME_LENGTH = 100
