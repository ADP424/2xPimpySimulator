-- SERVERS
CREATE TABLE servers (
    discord_id                  BIGINT PRIMARY KEY,
    event_channel_discord_id    BIGINT NULL,
    joined_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- OWNERS (players)
CREATE TABLE owners (
    discord_id      BIGINT NOT NULL PRIMARY KEY,
    dollars         INTEGER NOT NULL DEFAULT 100,
    bloodskulls     INTEGER NOT NULL DEFAULT 0,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- OWNER SERVERS
CREATE TABLE owner_servers (
    server_discord_id   BIGINT NOT NULL REFERENCES servers(discord_id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    PRIMARY KEY (server_discord_id, owner_discord_id)
);


-- VENDORS (NPCs)
CREATE TABLE vendors (
    id                  BIGSERIAL PRIMARY KEY,
    server_discord_id   BIGINT NOT NULL REFERENCES servers(discord_id) ON DELETE CASCADE,
    name                TEXT NOT NULL,

    desired_mutation_1  BIGINT NULL REFERENCES mutations(id),
    desired_mutation_2  BIGINT NULL REFERENCES mutations(id),
    desired_mutation_3  BIGINT NULL REFERENCES mutations(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (server_discord_id, name)
);


-- POOCHES
CREATE TABLE pooches (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL,
    age                 INTEGER NOT NULL DEFAULT 0,
    sex                 sex NOT NULL,
    base_health         INTEGER NOT NULL DEFAULT 10,
    health_loss_age     INTEGER NOT NULL DEFAULT 0,

    breeding_cooldown   INTEGER NOT NULL DEFAULT 2,
    alive               BOOLEAN NOT NULL DEFAULT TRUE,
    virgin              BOOLEAN NOT NULL DEFAULT TRUE,

    owner_discord_id    BIGINT NULL REFERENCES owners(discord_id) ON DELETE SET NULL,
    vendor_id           BIGINT NULL REFERENCES vendors(id) ON DELETE SET NULL,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- a pooch cannot be owned by both a player and vendor at the same time
    CONSTRAINT pooch_owner_xor_vendor CHECK (
        (owner_discord_id IS NULL) OR (vendor_id IS NULL)
    ),

    CONSTRAINT pooch_age_minimum CHECK (age >= -1),
    CONSTRAINT pooch_base_health_minimum CHECK (base_health >= 0),
    CONSTRAINT pooch_breeding_cooldown_minimum CHECK (breeding_cooldown >= 0)
);


-- POOCH RELATIONS (parents and pregnancies)
CREATE TABLE pooch_parentage (
    child_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    father_id   BIGINT NULL REFERENCES pooches(id) ON DELETE SET NULL,
    mother_id   BIGINT NULL REFERENCES pooches(id) ON DELETE SET NULL,

    CONSTRAINT no_self_parent CHECK (child_id <> father_id AND child_id <> mother_id),
    CONSTRAINT no_duplicate_parents CHECK (father_id IS NULL OR mother_id IS NULL OR father_id <> mother_id)
);

CREATE TABLE pooch_pregnancy (
    mother_id   BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,
    fetus_id    BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,

    PRIMARY KEY (mother_id, fetus_id),
    UNIQUE (fetus_id),

    CONSTRAINT no_self_fetus CHECK (mother_id <> fetus_id)
);


-- POOCH BREEDS
CREATE TABLE pooch_breeds (
    pooch_id    BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,
    breed_id    BIGINT NOT NULL REFERENCES breeds(id) ON DELETE RESTRICT,
    weight      INTEGER NOT NULL,

    PRIMARY KEY (pooch_id, breed_id)
);


-- POOCH MUTATIONS
CREATE TABLE pooch_mutations (
    pooch_id    BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,
    mutation_id BIGINT NOT NULL REFERENCES mutations(id) ON DELETE RESTRICT,

    PRIMARY KEY (pooch_id, mutation_id)
);


-- KENNELS
CREATE TABLE kennels (
    id                  BIGSERIAL PRIMARY KEY,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    name                TEXT NOT NULL,
    pooch_limit         INTEGER NOT NULL DEFAULT 10,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- KENNEL POOCHES
CREATE TABLE kennel_pooches (
    pooch_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    kennel_id   BIGINT NOT NULL REFERENCES kennels(id) ON DELETE CASCADE
);


-- GRAVEYARDS (one per owner)
CREATE TABLE graveyard_pooches (
    pooch_id            BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    buried_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- VENDOR POOCHES FOR SALE
CREATE TABLE vendor_pooches_for_sale (
    pooch_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    vendor_id   BIGINT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE
);


-- HELL
CREATE TABLE hell_pooches (
    pooch_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,

    damned_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
