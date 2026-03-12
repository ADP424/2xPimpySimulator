-- KENNELS
CREATE TABLE kennels (
    id                  BIGSERIAL PRIMARY KEY,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    name                TEXT NOT NULL,
    pooch_limit         INTEGER NOT NULL DEFAULT 10,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- KENNEL POOCHES
CREATE TABLE kennel_pooches (
    pooch_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    kennel_id   BIGINT NOT NULL REFERENCES kennels(id) ON DELETE CASCADE
);
