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

    -- Snapshot of the owner's event context at first participation
    context                 JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- All individual option submissions across all menus, stored as a JSONB array.
    -- Each element: {
    --   "menu_name": str, "menu_option_id": int, "option_label": str,
    --   "selected_pooch_id": int|null, "context_snapshot": {...},
    --   "score_contribution": float, "immediate_result": {...}, "submitted_at": str (ISO)
    -- }
    submissions             JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Immediate result from the first option actions (kept for backwards display compat)
    immediate_result        JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolution_result       JSONB NOT NULL DEFAULT '{}'::jsonb,

    score                   DOUBLE PRECISION NULL,
    rank                    INTEGER NULL,
    participated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT server_event_one_entry_per_owner UNIQUE (occurrence_id, owner_discord_id)
);
