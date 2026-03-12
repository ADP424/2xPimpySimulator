import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

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


def _execute_sql_file(cur: psycopg.Cursor, path: Path):
    cur.execute(path.read_text(encoding="utf-8"))


def _iter_schema_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.sql") if path.is_file())


def main():
    load_dotenv()

    schema_directory = Path(__file__).parent.parent / "schema"
    static_directory = schema_directory / "static"
    main_directory = schema_directory / "main"

    with psycopg.connect(_get_sync_dsn(), autocommit=True) as conn:
        logger.info("Wiping database and loading schema files...")

        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            _execute_sql_file(cur, schema_directory / "enums.sql")
            for path in _iter_schema_files(static_directory):
                _execute_sql_file(cur, path)
            for path in _iter_schema_files(main_directory):
                _execute_sql_file(cur, path)

        logger.info("Finished wiping database and loading schema files.")


if __name__ == "__main__":
    main()
