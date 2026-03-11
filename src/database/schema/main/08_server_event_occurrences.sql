-- ACTIVE / ARCHIVED SERVER EVENT OCCURRENCES
CREATE TABLE server_event_occurrences (
    id                      BIGSERIAL PRIMARY KEY,
    server_discord_id       BIGINT NOT NULL REFERENCES servers(discord_id) ON DELETE CASCADE,
    server_event_id         BIGINT NOT NULL REFERENCES server_events(id) ON DELETE CASCADE,

    context                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary          JSONB NOT NULL DEFAULT '{}'::jsonb,

    triggered_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at              TIMESTAMPTZ NOT NULL,
    resolved_at             TIMESTAMPTZ NULL,

    message_discord_id      BIGINT NULL,
    archived                BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE server_event_participations (
    id                      BIGSERIAL PRIMARY KEY,
    occurrence_id           BIGINT NOT NULL REFERENCES server_event_occurrences(id) ON DELETE CASCADE,
    owner_discord_id        BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,
    selected_option_id      BIGINT NOT NULL REFERENCES server_event_options(id) ON DELETE CASCADE,

    context                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    immediate_result        JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolution_result       JSONB NOT NULL DEFAULT '{}'::jsonb,

    score                   DOUBLE PRECISION NULL,
    rank                    INTEGER NULL,
    participated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (occurrence_id, owner_discord_id)
);
