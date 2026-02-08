-- SERVERS
CREATE TABLE servers (
    id                  BIGINT PRIMARY KEY,
    event_channel_id    BIGINT NULL,
    joined_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- OWNERS (players)
CREATE TABLE owners (
    server_id       BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    discord_id      BIGINT NOT NULL,
    dollars         INTEGER NOT NULL DEFAULT 100,
    bloodskulls     INTEGER NOT NULL DEFAULT 0,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (server_id, discord_id)
);


-- VENDORS (NPCs)
CREATE TABLE vendors (
    id                  BIGSERIAL PRIMARY KEY,
    server_id           BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,

    desired_mutation_1  BIGINT NULL REFERENCES mutations(id),
    desired_mutation_2  BIGINT NULL REFERENCES mutations(id),
    desired_mutation_3  BIGINT NULL REFERENCES mutations(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (server_id, id),
    UNIQUE (server_id, name)
);


-- POOCHES
CREATE TABLE pooches (
    id                  BIGSERIAL PRIMARY KEY,
    server_id           BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,

    name                TEXT NOT NULL,
    age                 INTEGER NOT NULL DEFAULT 0,
    sex                 sex NOT NULL,
    base_health         INTEGER NOT NULL DEFAULT 8,
    health_loss_age     INTEGER NOT NULL DEFAULT 0,

    breeding_cooldown   INTEGER NOT NULL DEFAULT 2,
    alive               BOOLEAN NOT NULL DEFAULT TRUE,
    virgin              BOOLEAN NOT NULL DEFAULT TRUE,

    owner_discord_id    BIGINT NULL,
    vendor_id           BIGINT NULL,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (server_id, id),

    FOREIGN KEY (server_id, owner_discord_id) REFERENCES owners(server_id, discord_id) ON DELETE SET NULL,
    FOREIGN KEY (server_id, vendor_id) REFERENCES vendors(server_id, id) ON DELETE SET NULL,

    -- a pooch cannot be owned by both a player and vendor at the same time
    CONSTRAINT pooch_owner_xor_vendor CHECK (
        (owner_discord_id IS NOT NULL AND vendor_id IS NULL)
        OR (owner_discord_id IS NULL AND vendor_id IS NOT NULL)
        OR (owner_discord_id IS NULL AND vendor_id IS NULL)
    ),

    CONSTRAINT pooch_age_minimum CHECK (age >= -1),
    CONSTRAINT pooch_base_health_minimum CHECK (base_health >= 0),
    CONSTRAINT pooch_breeding_cooldown_minimum CHECK (breeding_cooldown >= 0)
);


-- POOCH RELATIONS (parents and pregnancies)
CREATE TABLE pooch_parentage (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    pooch_id    BIGINT NOT NULL,
    father_id   BIGINT NULL,
    mother_id   BIGINT NULL,

    PRIMARY KEY (server_id, pooch_id),

    FOREIGN KEY (server_id, pooch_id)  REFERENCES pooches(server_id, id) ON DELETE CASCADE,
    FOREIGN KEY (server_id, father_id) REFERENCES pooches(server_id, id) ON DELETE SET NULL,
    FOREIGN KEY (server_id, mother_id) REFERENCES pooches(server_id, id) ON DELETE SET NULL,

    CONSTRAINT no_self_parent CHECK (pooch_id <> father_id AND pooch_id <> mother_id),
    CONSTRAINT no_duplicate_parents CHECK (father_id IS NULL OR mother_id IS NULL OR father_id <> mother_id)
);

CREATE TABLE pooch_pregnancy (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    pooch_id    BIGINT NOT NULL,
    fetus_id    BIGINT NOT NULL,

    PRIMARY KEY (server_id, pooch_id, fetus_id),
    UNIQUE (server_id, fetus_id),

    FOREIGN KEY (server_id, pooch_id) REFERENCES pooches(server_id, id) ON DELETE CASCADE,
    FOREIGN KEY (server_id, fetus_id) REFERENCES pooches(server_id, id) ON DELETE CASCADE,

    CONSTRAINT no_self_fetus CHECK (pooch_id <> fetus_id)
);


-- POOCH BREEDS
CREATE TABLE pooch_breeds (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    pooch_id    BIGINT NOT NULL,
    breed_id    BIGINT NOT NULL REFERENCES breeds(id) ON DELETE RESTRICT,
    weight      INTEGER NOT NULL,

    PRIMARY KEY (server_id, pooch_id, breed_id),

    FOREIGN KEY (server_id, pooch_id) REFERENCES pooches(server_id, id) ON DELETE CASCADE
);


-- POOCH MUTATIONS
CREATE TABLE pooch_mutations (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    pooch_id    BIGINT NOT NULL,
    mutation_id BIGINT NOT NULL REFERENCES mutations(id) ON DELETE RESTRICT,

    PRIMARY KEY (server_id, pooch_id, mutation_id),

    FOREIGN KEY (server_id, pooch_id) REFERENCES pooches(server_id, id) ON DELETE CASCADE
);


-- KENNELS
CREATE TABLE kennels (
    id                  BIGSERIAL PRIMARY KEY,
    server_id           BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL,
    name                TEXT NOT NULL,
    pooch_limit         INTEGER NOT NULL DEFAULT 10,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (server_id, id),

    FOREIGN KEY (server_id, owner_discord_id) REFERENCES owners(server_id, discord_id) ON DELETE CASCADE
);


-- KENNEL POOCHES
CREATE TABLE kennel_pooches (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    kennel_id   BIGINT NOT NULL,
    pooch_id    BIGINT NOT NULL,

    PRIMARY KEY (server_id, kennel_id, pooch_id),

    FOREIGN KEY (server_id, kennel_id) REFERENCES kennels(server_id, id) ON DELETE CASCADE,
    FOREIGN KEY (server_id, pooch_id)  REFERENCES pooches(server_id, id) ON DELETE RESTRICT
);


-- GRAVEYARDS (one per owner)
CREATE TABLE graveyard_pooches (
    server_id           BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL,
    pooch_id            BIGINT NOT NULL,
    buried_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (server_id, owner_discord_id, pooch_id),

    FOREIGN KEY (server_id, owner_discord_id) REFERENCES owners(server_id, discord_id) ON DELETE CASCADE,
    FOREIGN KEY (server_id, pooch_id) REFERENCES pooches(server_id, id) ON DELETE RESTRICT
);


-- VENDOR POOCHES FOR SALE
CREATE TABLE vendor_pooches_for_sale (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    vendor_id   BIGINT NOT NULL,
    pooch_id    BIGINT NOT NULL,

    PRIMARY KEY (server_id, vendor_id, pooch_id),
    UNIQUE (server_id, pooch_id),

    FOREIGN KEY (server_id, vendor_id) REFERENCES vendors(server_id, id) ON DELETE CASCADE,
    FOREIGN KEY (server_id, pooch_id)  REFERENCES pooches(server_id, id) ON DELETE RESTRICT
);


-- HELL (one per server)
CREATE TABLE hell_pooches (
    server_id   BIGINT NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    pooch_id    BIGINT NOT NULL,
    damned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (server_id, pooch_id),

    FOREIGN KEY (server_id, pooch_id) REFERENCES pooches(server_id, id) ON DELETE RESTRICT
);
