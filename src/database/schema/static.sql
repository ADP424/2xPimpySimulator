-- BREEDS (statically loaded from resources/breeds.json)
CREATE TABLE breeds (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    alt_name        TEXT NOT NULL,
    category        TEXT NOT NULL,
    description     TEXT NOT NULL,
    rarity          rarity NOT NULL DEFAULT 'common'
);


-- MUTATIONS (statically loaded from resources/mutations.json)
CREATE TABLE mutations (
    id                          BIGSERIAL PRIMARY KEY,
    name                        TEXT NOT NULL UNIQUE,
    alt_name                    TEXT NOT NULL,
    category                    TEXT NOT NULL,
    description                 TEXT NOT NULL,
    heritability                NUMERIC(4,3) NOT NULL DEFAULT 0.25, -- doubled when both parents have it
    health_impact               health_impact NOT NULL DEFAULT 'neutral',
    rarity                      rarity NOT NULL DEFAULT 'common',
    affects_males               BOOLEAN NOT NULL DEFAULT TRUE,
    affects_females             BOOLEAN NOT NULL DEFAULT TRUE,
    advanced_options            JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT bounded_heritability CHECK (heritability BETWEEN 0 AND 1)
);


-- DOG NAMES (statically loaded from resources/dog_names.txt)
CREATE TABLE dog_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);


-- VENDOR FIRST NAMES (statically loaded from resources/vendor_first_names.txt)
CREATE TABLE vendor_first_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);


-- VENDOR LAST NAMES (statically loaded from resources/vendor_last_names.txt)
CREATE TABLE vendor_last_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);
