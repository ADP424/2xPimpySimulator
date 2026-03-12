-- VENDORS (NPCs)
CREATE TABLE vendors (
    id                  BIGSERIAL PRIMARY KEY,
    server_discord_id   BIGINT NOT NULL REFERENCES servers(discord_id) ON DELETE CASCADE,

    name                TEXT NOT NULL,
    price_markup        NUMERIC(4,3) NOT NULL DEFAULT 1.0,

    desired_mutation_1  BIGINT NULL REFERENCES mutations(id),
    desired_mutation_2  BIGINT NULL REFERENCES mutations(id),
    desired_mutation_3  BIGINT NULL REFERENCES mutations(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (server_discord_id, name)
);
