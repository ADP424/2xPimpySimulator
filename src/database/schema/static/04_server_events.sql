-- SERVER EVENTS (statically loaded from resources/server_events/**/*.jsonc)
CREATE TABLE server_events (
    id                      BIGSERIAL PRIMARY KEY,

    name                    TEXT NOT NULL UNIQUE,
    category                TEXT NOT NULL,
    description             TEXT NOT NULL,
    flavor_text             TEXT NOT NULL DEFAULT '',

    severity                event_severity NOT NULL DEFAULT 'moderate',
    rarity                  rarity NOT NULL DEFAULT 'common',

    min_owners              INTEGER NOT NULL DEFAULT 1,
    max_participants        INTEGER NOT NULL DEFAULT 0,
    resolution_strategy     TEXT NOT NULL DEFAULT 'random_winner',

    parameters        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE server_event_options (
    id                      BIGSERIAL PRIMARY KEY,
    server_event_id         BIGINT NOT NULL REFERENCES server_events(id) ON DELETE CASCADE,

    option_order            INTEGER NOT NULL DEFAULT 0,
    label                   TEXT NOT NULL,
    description             TEXT NOT NULL DEFAULT '',

    min_money               INTEGER NOT NULL DEFAULT 0,
    min_bloodskulls         INTEGER NOT NULL DEFAULT 0,
    requires_pooch_selection BOOLEAN NOT NULL DEFAULT FALSE,

    parameters        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE server_event_outcomes (
    id                      BIGSERIAL PRIMARY KEY,
    server_event_id         BIGINT NOT NULL REFERENCES server_events(id) ON DELETE CASCADE,

    outcome_order           INTEGER NOT NULL DEFAULT 0,
    label                   TEXT NOT NULL DEFAULT '',
    description             TEXT NOT NULL DEFAULT '',
    message                 TEXT NOT NULL DEFAULT '',
    min_rank                INTEGER,
    max_rank                INTEGER,
    chance                  DOUBLE PRECISION,

    parameters        JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT server_event_outcomes_chance_range CHECK (chance IS NULL OR (chance >= 0 AND chance <= 1)),
    CONSTRAINT server_event_outcomes_rank_bounds CHECK (
        (min_rank IS NULL OR min_rank >= 1) AND
        (max_rank IS NULL OR max_rank >= 1) AND
        (min_rank IS NULL OR max_rank IS NULL OR min_rank <= max_rank)
    )
);
