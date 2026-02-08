from sqlalchemy.dialects.postgresql import ENUM

RARITY = ENUM(
    "common",
    "uncommon",
    "novel",
    "rare",
    "unprecedented",
    "remarkable",
    "extraordinary",
    "unique",
    name="rarity",
    create_type=False,
)
