-- POOCHES
CREATE TABLE pooches (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL,
    age                 INTEGER NOT NULL DEFAULT 0,
    sex                 sex NOT NULL,
    base_health         INTEGER NOT NULL DEFAULT 10,
    health_loss_age     INTEGER NOT NULL DEFAULT 0,

    strength            INTEGER NOT NULL DEFAULT 10,
    cuteness            INTEGER NOT NULL DEFAULT 10,
    fluffiness          INTEGER NOT NULL DEFAULT 10,
    intelligence        INTEGER NOT NULL DEFAULT 10,
    dexterity           INTEGER NOT NULL DEFAULT 10,
    fertility           INTEGER NOT NULL DEFAULT 10,
    aggressiveness      INTEGER NOT NULL DEFAULT 10,
    constitution        INTEGER NOT NULL DEFAULT 10,

    size                INTEGER NOT NULL DEFAULT 10,

    breeding_cooldown   INTEGER NOT NULL DEFAULT 2,
    alive               BOOLEAN NOT NULL DEFAULT TRUE,
    virgin              BOOLEAN NOT NULL DEFAULT TRUE,

    owner_discord_id    BIGINT NULL REFERENCES owners(discord_id) ON DELETE SET NULL,
    vendor_id           BIGINT NULL REFERENCES vendors(id) ON DELETE SET NULL,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pooch_owner_xor_vendor CHECK ((owner_discord_id IS NULL) OR (vendor_id IS NULL)),
    CONSTRAINT pooch_age_minimum CHECK (age >= -1),
    CONSTRAINT pooch_base_health_minimum CHECK (base_health >= 0),
    CONSTRAINT pooch_strength_minimum CHECK (strength >= 0),
    CONSTRAINT pooch_cuteness_minimum CHECK (cuteness >= 0),
    CONSTRAINT pooch_fluffiness_minimum CHECK (fluffiness >= 0),
    CONSTRAINT pooch_intelligence_minimum CHECK (intelligence >= 0),
    CONSTRAINT pooch_dexterity_minimum CHECK (dexterity >= 0),
    CONSTRAINT pooch_fertility_minimum CHECK (fertility >= 0),
    CONSTRAINT pooch_aggressiveness_minimum CHECK (aggressiveness >= 0),
    CONSTRAINT pooch_constitution_minimum CHECK (constitution >= 0),
    CONSTRAINT pooch_size_minimum CHECK (size >= 0),
    CONSTRAINT pooch_breeding_cooldown_minimum CHECK (breeding_cooldown >= 0)
);
