-- GRAVEYARD
CREATE TABLE graveyard_pooches (
    pooch_id            BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    owner_discord_id    BIGINT NOT NULL REFERENCES owners(discord_id) ON DELETE CASCADE,

    buried_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- VENDOR POOCHES FOR SALE
CREATE TABLE vendor_pooches_for_sale (
    pooch_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    vendor_id   BIGINT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE
);

-- HELL
CREATE TABLE hell_pooches (
    pooch_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,

    damned_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
