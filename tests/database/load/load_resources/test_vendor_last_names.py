"""Tests for src/database/load/load_resources/vendor_last_names.py."""

from unittest.mock import AsyncMock, MagicMock, patch


async def test_load_vendor_last_names_loads_names():
    """load_vendor_last_names should clear and insert vendor last names."""
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
            "src.database.load.load_resources.vendor_last_names.load_names_from_root", return_value=["Smith", "Jones"]
        ),
        patch(
            "src.database.load.load_resources.vendor_last_names.validate_name_list",
            side_effect=lambda name, items: items,
        ),
        patch("src.database.load.load_resources.vendor_last_names.session_scope", return_value=_FakeScope()),
    ):
        from src.database.load.load_resources.vendor_last_names import (
            load_vendor_last_names,
        )

        await load_vendor_last_names()

    mock_session.execute.assert_awaited_once()
    assert len(added) == 2


async def test_load_vendor_last_names_empty():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()

    class _FakeScope:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    with (
        patch("src.database.load.load_resources.vendor_last_names.load_names_from_root", return_value=[]),
        patch("src.database.load.load_resources.vendor_last_names.validate_name_list", return_value=[]),
        patch("src.database.load.load_resources.vendor_last_names.session_scope", return_value=_FakeScope()),
    ):
        from src.database.load.load_resources.vendor_last_names import (
            load_vendor_last_names,
        )

        await load_vendor_last_names()

    mock_session.add.assert_not_called()
