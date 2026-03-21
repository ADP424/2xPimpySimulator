-- OWNER EVENTS (statically loaded from resources/owner_events/**/*.jsonc)
CREATE TABLE owner_events (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL UNIQUE,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,
    flavor_text         TEXT NOT NULL DEFAULT '',

    severity            event_severity NOT NULL DEFAULT 'moderate',
    rarity              rarity NOT NULL DEFAULT 'common',

    requires_response   BOOLEAN NOT NULL DEFAULT FALSE,
    response_timeout    INTEGER NOT NULL DEFAULT 3600,

    triggered_only      BOOLEAN NOT NULL DEFAULT FALSE,

    filter              JSONB NOT NULL DEFAULT '{}'::jsonb,
    parameters    JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE owner_event_options (
    id                  BIGSERIAL PRIMARY KEY,
    event_id            BIGINT NOT NULL REFERENCES owner_events(id) ON DELETE CASCADE,

    option_order        INTEGER NOT NULL DEFAULT 0,
    label               TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',

    is_default          BOOLEAN NOT NULL DEFAULT FALSE,
    is_visible          BOOLEAN NOT NULL DEFAULT TRUE,

    filter              JSONB NOT NULL DEFAULT '{}'::jsonb,
    parameters    JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE owner_event_outcomes (
    id                  BIGSERIAL PRIMARY KEY,
    option_id           BIGINT NOT NULL REFERENCES owner_event_options(id) ON DELETE CASCADE,

    outcome_order       INTEGER NOT NULL DEFAULT 0,
    label               TEXT NOT NULL DEFAULT '',
    description         TEXT NOT NULL DEFAULT '',
    message             TEXT NOT NULL DEFAULT '',
    chance              DOUBLE PRECISION,

    parameters    JSONB NOT NULL DEFAULT '{}'::jsonb,
    stat_weights        JSONB NOT NULL DEFAULT '[]'::jsonb,

    CONSTRAINT owner_event_outcomes_chance_range CHECK (chance IS NULL OR (chance >= 0 AND chance <= 1))
);
