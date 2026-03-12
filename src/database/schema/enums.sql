-- SEX (for pooches)
CREATE TYPE sex AS ENUM (
    'female',
    'male'
);


-- RARITY (for breeds and mutations)
CREATE TYPE rarity AS ENUM (
    'common',
    'uncommon',
    'novel',
    'rare',
    'unprecedented',
    'remarkable',
    'extraordinary',
    'unique'
);

CREATE TABLE rarity_weights (
    rarity rarity   PRIMARY KEY,
    weight integer  NOT NULL
);
INSERT INTO rarity_weights VALUES
    ('common', 1000),
    ('uncommon', 250),
    ('novel', 100),
    ('rare', 50),
    ('unprecedented', 25),
    ('remarkable', 10),
    ('extraordinary', 5),
    ('unique', 1)
;


-- HEALTH IMPACT (for mutations)
CREATE TYPE health_impact AS ENUM (
    'instant_death',
    'fatal',
    'brutal',
    'severe',
    'unhealthy',
    'harmful',

    'neutral',

    'helpful',
    'healthy',
    'great',
    'fantastic',
    'brilliant',
    'immortality'
);

CREATE TABLE health_impact_weights (
    health_impact   health_impact PRIMARY KEY,
    weight integer  NOT NULL
);
INSERT INTO health_impact_weights VALUES
    ('instant_death', -1000),
    ('fatal', -5),
    ('brutal', -4),
    ('severe', -3),
    ('unhealthy', -2),
    ('harmful', -1),

    ('neutral', 0),

    ('helpful', 1),
    ('healthy', 2),
    ('great', 3),
    ('fantastic', 4),
    ('brilliant', 5),
    ('immortality', 1000)
;


-- EVENT SEVERITY
CREATE TYPE event_severity AS ENUM (
    'trivial',
    'minor',
    'moderate',
    'major',
    'critical',
    'catastrophic'
);


-- EVENT TARGET TYPE (what an event affects)
CREATE TYPE event_target_type AS ENUM (
    'owner',
    'pooch',
    'kennel'
);


-- EVENT ACTION TYPE (what happens to an event's target)
CREATE TYPE event_action_type AS ENUM (
    'modify_money',
    'modify_bloodskulls',
    'modify_pooch_health',
    'modify_pooch_age',
    'kill_pooch',
    'add_mutation',
    'remove_mutation',
    'add_breed',
    'transfer_pooch',
    'create_pooch',
    'clone_pooch',
    'modify_kennel_capacity',
    'rename_pooch',
    'set_breeding_cooldown',
    'start_event',
    'breed_pooches'
);
