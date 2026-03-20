"""Tests for src/database/load/load_resources/dog_names.py."""

from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# load_dog_names
# ---------------------------------------------------------------------------


async def test_load_dog_names_loads_names():
    """load_dog_names should delete existing and insert new dog names."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    added = []
    mock_session.add = MagicMock(side_effect=lambda obj: added.append(obj))

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with (
        patch(
            "src.database.load.load_resources.dog_names.load_names_from_root", return_value=["Buddy", "Max", "Bella"]
        ),
        patch("src.database.load.load_resources.dog_names.validate_name_list", side_effect=lambda name, items: items),
        patch("src.database.load.load_resources.dog_names.session_scope", return_value=_FakeScope()),
    ):
        from src.database.load.load_resources.dog_names import load_dog_names

        await load_dog_names()

    # Should have cleared the table then added 3 names
    mock_session.execute.assert_awaited_once()
    assert len(added) == 3


async def test_load_dog_names_empty_list():
    """If no dog names are found, nothing should be added."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with (
        patch("src.database.load.load_resources.dog_names.load_names_from_root", return_value=[]),
        patch("src.database.load.load_resources.dog_names.validate_name_list", return_value=[]),
        patch("src.database.load.load_resources.dog_names.session_scope", return_value=_FakeScope()),
    ):
        from src.database.load.load_resources.dog_names import load_dog_names

        await load_dog_names()

    mock_session.add.assert_not_called()
