import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from logger import get_logger

logger = get_logger("database/load/reset_database")


def _get_sync_dsn() -> str:
    return (
        f"dbname={os.environ['DATABASE']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']} "
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ.get('DB_PORT', '5432')}"
    )


def _execute_sql_file(cur: psycopg.Cursor, path: Path):
    cur.execute(path.read_text(encoding="utf-8"))


def main():
    load_dotenv()

    schema_directory = Path(__file__).parent.parent / "schema"
    with psycopg.connect(_get_sync_dsn(), autocommit=True) as conn:
        logger.info("Wiping database and loading the schema file...")

        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            _execute_sql_file(cur, schema_directory / "enums.sql")
            _execute_sql_file(cur, schema_directory / "static.sql")
            _execute_sql_file(cur, schema_directory / "main.sql")

        logger.info("Finished wiping database and loading the schema file.")


if __name__ == "__main__":
    main()
