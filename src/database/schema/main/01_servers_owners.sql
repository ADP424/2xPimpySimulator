-- SERVERS
CREATE TABLE servers (
    discord_id                  BIGINT PRIMARY KEY,
    event_channel_discord_id    BIGINT NULL,
    joined_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- OWNERS (players)
CREATE TABLE owners (
    discord_id      BIGINT NOT NULL PRIMARY KEY,
    discord_name    TEXT NULL,
    dollars         INTEGER NOT NULL DEFAULT 100,
    bloodskulls     INTEGER NOT NULL DEFAULT 0,
    begged_today    BOOLEAN NOT NULL DEFAULT TRUE,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- OWNER SERVERS
CREATE TABLE owner_servers (
    server_discord_id   BIGINT NOT NULL REFERENCES servers(discord_id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    PRIMARY KEY (server_discord_id, owner_discord_id)
);
