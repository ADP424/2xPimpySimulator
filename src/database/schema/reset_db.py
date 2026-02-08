from pathlib import Path
from dotenv import load_dotenv
import os
import psycopg

load_dotenv()


def _get_sync_dsn() -> str:
    return (
        f"dbname={os.environ['DATABASE']} "
        f"user={os.environ['USER']} "
        f"password={os.environ['PASSWORD']} "
        f"host={os.environ['HOST']} "
        f"port={os.environ.get('PORT', '5432')}"
    )


def _execute_sql_file(cur: psycopg.Cursor, path: Path):
    cur.execute(path.read_text(encoding="utf-8"))


def main():
    schema_directory = Path(__file__).parent

    with psycopg.connect(_get_sync_dsn(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            _execute_sql_file(cur, schema_directory / "enums.sql")
            _execute_sql_file(cur, schema_directory / "static.sql")
            _execute_sql_file(cur, schema_directory / "main.sql")


if __name__ == "__main__":
    main()
