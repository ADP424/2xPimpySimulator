-- BREEDS (statically loaded from resources/breeds/**/*.jsonc)
CREATE TABLE breeds (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL UNIQUE,
    alt_name            TEXT NOT NULL,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,

    rarity              rarity NOT NULL DEFAULT 'common',
    min_size            INTEGER NOT NULL DEFAULT 8,
    max_size            INTEGER NOT NULL DEFAULT 12,

    parameters          JSONB NOT NULL DEFAULT '{}'::jsonb
);


-- MUTATIONS (statically loaded from resources/mutations/**/*.jsonc)
CREATE TABLE mutations (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL UNIQUE,
    alt_name            TEXT NOT NULL,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,

    heritability        NUMERIC(4,3) NOT NULL DEFAULT 0.25,

    health_impact       health_impact NOT NULL DEFAULT 'neutral',
    rarity              rarity NOT NULL DEFAULT 'common',

    affects_females     BOOLEAN NOT NULL DEFAULT TRUE,
    affects_males       BOOLEAN NOT NULL DEFAULT TRUE,

    parameters          JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT bounded_heritability CHECK (heritability BETWEEN 0 AND 1)
);
