import os

import psycopg
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from src.database.models import Base
from src.logger import get_logger

logger = get_logger("database/load/reset_database")


def _get_sync_dsn() -> str:
    return (
        f"dbname={os.environ['DATABASE']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']} "
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ.get('DB_PORT', '5432')}"
    )


def _get_sqlalchemy_url() -> str:
    return (
        f"postgresql+psycopg://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}/{os.environ['DATABASE']}"
    )


_RARITY_WEIGHTS = [
    ("common", 1000),
    ("uncommon", 250),
    ("novel", 100),
    ("rare", 50),
    ("unprecedented", 25),
    ("remarkable", 10),
    ("extraordinary", 5),
    ("unique", 1),
]

_HEALTH_IMPACT_WEIGHTS = [
    ("instant_death", -1000),
    ("fatal", -5),
    ("brutal", -4),
    ("severe", -3),
    ("unhealthy", -2),
    ("harmful", -1),
    ("neutral", 0),
    ("helpful", 1),
    ("healthy", 2),
    ("great", 3),
    ("fantastic", 4),
    ("brilliant", 5),
    ("immortality", 1000),
]


def main():
    load_dotenv()

    dsn = _get_sync_dsn()
    logger.info("Wiping database and recreating schema from ORM metadata...")

    # Step 1: Drop and recreate the public schema (wipes all tables and types)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")

    # Step 2: Use SQLAlchemy to create all tables (and ENUM types, since create_type=True)
    engine = create_engine(_get_sqlalchemy_url())
    Base.metadata.create_all(engine)

    # Step 3: Seed static weight rows
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO rarity_weights (rarity, weight) VALUES (:rarity, :weight)"),
            [{"rarity": r, "weight": w} for r, w in _RARITY_WEIGHTS],
        )
        conn.execute(
            text("INSERT INTO health_impact_weights (health_impact, weight) VALUES (:health_impact, :weight)"),
            [{"health_impact": h, "weight": w} for h, w in _HEALTH_IMPACT_WEIGHTS],
        )
        conn.commit()

    logger.info("Database reset complete.")


if __name__ == "__main__":
    main()
