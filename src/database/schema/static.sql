-- BREEDS (statically loaded from resources/breeds/**/*.jsonc)
CREATE TABLE breeds (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL UNIQUE,
    alt_name            TEXT NOT NULL,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,

    rarity              rarity NOT NULL DEFAULT 'common',

    advanced_options    JSONB NOT NULL DEFAULT '{}'::jsonb
);


-- MUTATIONS (statically loaded from resources/mutations/**/*.jsonc)
CREATE TABLE mutations (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL UNIQUE,
    alt_name            TEXT NOT NULL,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,

    heritability        NUMERIC(4,3) NOT NULL DEFAULT 0.25,  -- doubled when both parents have it

    health_impact       health_impact NOT NULL DEFAULT 'neutral',
    rarity              rarity NOT NULL DEFAULT 'common',

    affects_females     BOOLEAN NOT NULL DEFAULT TRUE,
    affects_males       BOOLEAN NOT NULL DEFAULT TRUE,

    advanced_options    JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT bounded_heritability CHECK (heritability BETWEEN 0 AND 1)
);


-- DOG NAMES (statically loaded from resources/dog_names/**/*.txt)
CREATE TABLE dog_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);


-- VENDOR FIRST NAMES (statically loaded from resources/vendor_names/first/**/*.txt)
CREATE TABLE vendor_first_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);


-- VENDOR LAST NAMES (statically loaded from resources/vendor_names/last/**/*.txt)
CREATE TABLE vendor_last_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

-- EVENTS (statically loaded from resources/events/**/*.jsonc)
CREATE TABLE events (
    id                  BIGSERIAL PRIMARY KEY,

    name                TEXT NOT NULL UNIQUE,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,
    flavor_text         TEXT NOT NULL DEFAULT '',

    severity            event_severity NOT NULL DEFAULT 'moderate',
    rarity              rarity NOT NULL DEFAULT 'common',

    requires_response   BOOLEAN NOT NULL DEFAULT FALSE,
    response_timeout    INTEGER NOT NULL DEFAULT 3600,

    min_pooches         INTEGER NOT NULL DEFAULT 0,
    min_kennels         INTEGER NOT NULL DEFAULT 0,
    min_money           INTEGER NOT NULL DEFAULT 0,
    min_bloodskulls     INTEGER NOT NULL DEFAULT 0,
    triggered_only      BOOLEAN NOT NULL DEFAULT FALSE,

    advanced_options    JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- EVENT OPTIONS (player response options)
CREATE TABLE event_options (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,

    option_order    INTEGER NOT NULL DEFAULT 0,
    label           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',

    min_money       INTEGER NOT NULL DEFAULT 0,
    min_bloodskulls INTEGER NOT NULL DEFAULT 0,

    advanced_options JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- EVENT OUTCOMES (chance-based branches after selecting an option)
CREATE TABLE event_outcomes (
    id               BIGSERIAL PRIMARY KEY,
    option_id        BIGINT NOT NULL REFERENCES event_options(id) ON DELETE CASCADE,

    outcome_order    INTEGER NOT NULL DEFAULT 0,
    label            TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    message          TEXT NOT NULL DEFAULT '',
    chance           DOUBLE PRECISION,

    advanced_options JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT event_outcomes_chance_range CHECK (chance IS NULL OR (chance >= 0 AND chance <= 1))
);

-- EVENT ACTIONS (actions attached to an event, option, or outcome)
CREATE TABLE event_actions (
    id               BIGSERIAL PRIMARY KEY,
    event_id         BIGINT REFERENCES events(id) ON DELETE CASCADE,
    option_id        BIGINT REFERENCES event_options(id) ON DELETE CASCADE,
    outcome_id       BIGINT REFERENCES event_outcomes(id) ON DELETE CASCADE,

    action_order     INTEGER NOT NULL DEFAULT 0,
    action_type      event_action_type NOT NULL,
    target_type      event_target_type NOT NULL DEFAULT 'owner',

    parameters       JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT event_actions_exactly_one_parent CHECK (num_nonnulls(event_id, option_id, outcome_id) = 1)
);
