CREATE TABLE stray_events (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL,
    description TEXT NOT NULL,
    flavor_text TEXT NOT NULL DEFAULT '',

    severity    event_severity NOT NULL DEFAULT 'minor',
    rarity      rarity NOT NULL DEFAULT 'common',

    triggered_only BOOLEAN NOT NULL DEFAULT FALSE,

    filter          JSONB NOT NULL DEFAULT '{}'::jsonb,
    advanced_options JSONB NOT NULL DEFAULT '{}'::jsonb
);


CREATE TABLE stray_event_actions (
    id              BIGSERIAL PRIMARY KEY,
    stray_event_id  BIGINT NOT NULL REFERENCES stray_events(id) ON DELETE CASCADE,

    action_order    INTEGER NOT NULL DEFAULT 0,
    action_type     event_action_type NOT NULL,
    target_type     event_target_type NOT NULL DEFAULT 'pooch',
    repeat          INTEGER NOT NULL DEFAULT 1,

    parameters      JSONB NOT NULL DEFAULT '{}'::jsonb
);
