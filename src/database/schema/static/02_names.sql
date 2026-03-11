-- DOG NAMES (statically loaded from resources/dog_names/**/*.txt)
CREATE TABLE dog_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);


-- VENDOR FIRST NAMES (statically loaded from resources/vendor_names/first/**/*.txt)
CREATE TABLE vendor_first_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);


-- VENDOR LAST NAMES (statically loaded from resources/vendor_names/last/**/*.txt)
CREATE TABLE vendor_last_names (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);
