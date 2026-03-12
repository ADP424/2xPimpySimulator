-- OWNER EVENT OCCURRENCES (both active and archived events)
CREATE TABLE owner_event_occurrences (
    id                  BIGSERIAL PRIMARY KEY,

    event_id            BIGINT NOT NULL REFERENCES owner_events(id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    context             JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary      JSONB NOT NULL DEFAULT '{}'::jsonb,

    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NULL,
    responded_at        TIMESTAMPTZ NULL,
    completed_at        TIMESTAMPTZ NULL,

    selected_option_id  BIGINT NULL REFERENCES owner_event_options(id) ON DELETE SET NULL,
    timed_out           BOOLEAN NOT NULL DEFAULT FALSE,
    archived            BOOLEAN NOT NULL DEFAULT FALSE
);
