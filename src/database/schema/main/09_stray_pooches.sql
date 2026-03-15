CREATE TABLE stray_pooches (
    pooch_id            BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    server_discord_id   BIGINT NOT NULL REFERENCES servers(discord_id) ON DELETE CASCADE,
    released_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
