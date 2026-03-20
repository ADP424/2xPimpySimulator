"""Tests for src/database/load/reset_database.py."""

from unittest.mock import MagicMock


def test_iter_schema_files_returns_sorted_sql_files(tmp_path):
    from src.database.load.reset_database import _iter_schema_files

    (tmp_path / "02_table.sql").write_text("SELECT 1;")
    (tmp_path / "01_enums.sql").write_text("SELECT 1;")
    (tmp_path / "not_sql.txt").write_text("ignore me")

    result = _iter_schema_files(tmp_path)

    names = [p.name for p in result]
    assert names == ["01_enums.sql", "02_table.sql"]


def test_iter_schema_files_empty_directory(tmp_path):
    from src.database.load.reset_database import _iter_schema_files

    result = _iter_schema_files(tmp_path)

    assert result == []


def test_execute_sql_file_calls_execute(tmp_path):
    from src.database.load.reset_database import _execute_sql_file

    sql_file = tmp_path / "test.sql"
    sql_file.write_text("CREATE TABLE foo (id INT);")

    cursor = MagicMock()
    _execute_sql_file(cursor, sql_file)

    cursor.execute.assert_called_once_with("CREATE TABLE foo (id INT);")
