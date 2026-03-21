-- SERVER EVENTS (statically loaded from resources/server_events/**/*.jsonc)
CREATE TABLE server_events (
    id                      BIGSERIAL PRIMARY KEY,

    name                    TEXT NOT NULL UNIQUE,
    category                TEXT NOT NULL,
    description             TEXT NOT NULL,
    flavor_text             TEXT NOT NULL DEFAULT '',

    severity                event_severity NOT NULL DEFAULT 'moderate',
    rarity                  rarity NOT NULL DEFAULT 'common',
    tier                    TEXT NOT NULL DEFAULT 'minor',

    -- Eligibility filter (replaces min_owners / resolution_strategy)
    filter                  JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Default actions fired when no qualifying participants exist at resolution
    default_actions_data    JSONB NOT NULL DEFAULT '[]'::jsonb,

    parameters              JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE server_event_menus (
    id                      BIGSERIAL PRIMARY KEY,
    server_event_id         BIGINT NOT NULL REFERENCES server_events(id) ON DELETE CASCADE,

    menu_order              INTEGER NOT NULL DEFAULT 0,
    name                    TEXT NOT NULL,   -- slug used in depends_on and UI
    label                   TEXT NOT NULL DEFAULT '',
    description             TEXT NOT NULL DEFAULT '',

    -- -1 means unlimited
    max_uses_per_player     INTEGER NOT NULL DEFAULT 1,
    -- JSON list of menu name slugs that must be used before this menu becomes available
    depends_on              JSONB NOT NULL DEFAULT '[]'::jsonb,

    parameters              JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE server_event_menu_options (
    id                      BIGSERIAL PRIMARY KEY,
    menu_id                 BIGINT NOT NULL REFERENCES server_event_menus(id) ON DELETE CASCADE,

    option_order            INTEGER NOT NULL DEFAULT 0,
    label                   TEXT NOT NULL,
    description             TEXT NOT NULL DEFAULT '',

    -- OwnerEventFilterSpec as JSONB — controls who can see/use this option
    filter                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Requirements for submission (e.g. {"pooch": {"filter": {...}}})
    requires                JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- ScoringSpec as JSONB
    scoring                 JSONB NOT NULL DEFAULT '{}'::jsonb,

    parameters              JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE server_event_outcomes (
    id                      BIGSERIAL PRIMARY KEY,
    server_event_id         BIGINT NOT NULL REFERENCES server_events(id) ON DELETE CASCADE,

    outcome_order           INTEGER NOT NULL DEFAULT 0,
    label                   TEXT NOT NULL DEFAULT '',
    description             TEXT NOT NULL DEFAULT '',
    message                 TEXT NOT NULL DEFAULT '',
    -- "ranked_players" | "all_participants" | "server" | "non_participants"
    target                  TEXT NOT NULL DEFAULT 'ranked_players',
    min_rank                INTEGER,
    max_rank                INTEGER,
    chance                  DOUBLE PRECISION,

    parameters              JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT server_event_outcomes_chance_range CHECK (chance IS NULL OR (chance >= 0 AND chance <= 1)),
    CONSTRAINT server_event_outcomes_rank_bounds CHECK (
        (min_rank IS NULL OR min_rank >= 1) AND
        (max_rank IS NULL OR max_rank >= 1) AND
        (min_rank IS NULL OR max_rank IS NULL OR min_rank <= max_rank)
    )
);
