-- POOCH RELATIONS (parents and pregnancies)
CREATE TABLE pooch_parentage (
    child_id    BIGINT PRIMARY KEY REFERENCES pooches(id) ON DELETE CASCADE,
    father_id   BIGINT NULL REFERENCES pooches(id) ON DELETE SET NULL,
    mother_id   BIGINT NULL REFERENCES pooches(id) ON DELETE SET NULL,

    CONSTRAINT no_self_parent CHECK (child_id <> father_id AND child_id <> mother_id),
    CONSTRAINT no_duplicate_parents CHECK (father_id IS NULL OR mother_id IS NULL OR father_id <> mother_id)
);

CREATE TABLE pooch_pregnancy (
    mother_id   BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,
    fetus_id    BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,

    PRIMARY KEY (mother_id, fetus_id),
    UNIQUE (fetus_id),

    CONSTRAINT no_self_fetus CHECK (mother_id <> fetus_id)
);

CREATE TABLE pooch_breeds (
    pooch_id    BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,
    breed_id    BIGINT NOT NULL REFERENCES breeds(id) ON DELETE RESTRICT,
    weight      INTEGER NOT NULL,

    PRIMARY KEY (pooch_id, breed_id)
);

CREATE TABLE pooch_mutations (
    pooch_id    BIGINT NOT NULL REFERENCES pooches(id) ON DELETE CASCADE,
    mutation_id BIGINT NOT NULL REFERENCES mutations(id) ON DELETE RESTRICT,

    PRIMARY KEY (pooch_id, mutation_id)
);
