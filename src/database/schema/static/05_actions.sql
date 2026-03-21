-- EVENT ACTIONS shared by owner events and server events.
CREATE TABLE event_actions (
    id                              BIGSERIAL PRIMARY KEY,
    event_id                        BIGINT REFERENCES owner_events(id) ON DELETE CASCADE,
    option_id                       BIGINT REFERENCES owner_event_options(id) ON DELETE CASCADE,
    outcome_id                      BIGINT REFERENCES owner_event_outcomes(id) ON DELETE CASCADE,
    server_event_id                 BIGINT REFERENCES server_events(id) ON DELETE CASCADE,
    server_event_menu_option_id     BIGINT REFERENCES server_event_menu_options(id) ON DELETE CASCADE,
    server_event_outcome_id         BIGINT REFERENCES server_event_outcomes(id) ON DELETE CASCADE,

    action_order                    INTEGER NOT NULL DEFAULT 0,
    action_type                     TEXT NOT NULL,
    target_type                     TEXT NOT NULL DEFAULT 'owner',
    repeat                          INTEGER NOT NULL DEFAULT 1,

    parameters                      JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT event_actions_exactly_one_parent CHECK (
        num_nonnulls(event_id, option_id, outcome_id, server_event_id, server_event_menu_option_id, server_event_outcome_id) = 1
    )
);
