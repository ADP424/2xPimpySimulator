CREATE TABLE stray_events (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL,

    severity    event_severity NOT NULL DEFAULT 'minor',
    rarity      rarity NOT NULL DEFAULT 'common',

    triggered_only BOOLEAN NOT NULL DEFAULT FALSE,

    filter          JSONB NOT NULL DEFAULT '{}'::jsonb
);


CREATE TABLE stray_event_outcomes (
    id              BIGSERIAL PRIMARY KEY,
    stray_event_id  BIGINT NOT NULL REFERENCES stray_events(id) ON DELETE CASCADE,

    outcome_order   INTEGER NOT NULL DEFAULT 0,
    chance          DOUBLE PRECISION,
    stat_weights    JSONB NOT NULL DEFAULT '[]'::jsonb,

    CONSTRAINT stray_event_outcomes_chance_range CHECK (chance IS NULL OR (chance >= 0 AND chance <= 1))
);


CREATE TABLE stray_event_actions (
    id                      BIGSERIAL PRIMARY KEY,
    stray_event_id          BIGINT REFERENCES stray_events(id) ON DELETE CASCADE,
    stray_event_outcome_id  BIGINT REFERENCES stray_event_outcomes(id) ON DELETE CASCADE,

    action_order    INTEGER NOT NULL DEFAULT 0,
    action_type     event_action_type NOT NULL,
    repeat          INTEGER NOT NULL DEFAULT 1,

    parameters      JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT stray_event_actions_exactly_one_parent
        CHECK (num_nonnulls(stray_event_id, stray_event_outcome_id) = 1)
);
