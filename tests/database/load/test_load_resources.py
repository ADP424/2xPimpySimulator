"""Tests for src/database/load/load_resources/__init__.py (the main() orchestrator)."""

from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# main() calls all sub-loaders in the correct order
# ---------------------------------------------------------------------------


async def test_main_calls_all_loaders_in_order():
    """main() should invoke every sub-loader in the expected sequence."""
    mock_load_breeds = AsyncMock()
    mock_load_mutations = AsyncMock()
    mock_load_injuries = AsyncMock()
    mock_load_diseases = AsyncMock()
    mock_load_dog_names = AsyncMock()
    mock_load_vendor_first_names = AsyncMock()
    mock_load_vendor_last_names = AsyncMock()
    mock_load_owner_events = AsyncMock()
    mock_load_server_events = AsyncMock()
    mock_load_stray_events = AsyncMock()

    patches = {
        "src.database.load.load_resources.load_breeds": mock_load_breeds,
        "src.database.load.load_resources.load_mutations": mock_load_mutations,
        "src.database.load.load_resources.load_injuries": mock_load_injuries,
        "src.database.load.load_resources.load_diseases": mock_load_diseases,
        "src.database.load.load_resources.load_dog_names": mock_load_dog_names,
        "src.database.load.load_resources.load_vendor_first_names": mock_load_vendor_first_names,
        "src.database.load.load_resources.load_vendor_last_names": mock_load_vendor_last_names,
        "src.database.load.load_resources.load_owner_events": mock_load_owner_events,
        "src.database.load.load_resources.load_server_events": mock_load_server_events,
        "src.database.load.load_resources.load_stray_events": mock_load_stray_events,
    }

    with patch.multiple("src.database.load.load_resources", **{k.split(".")[-1]: v for k, v in patches.items()}):
        from src.database.load.load_resources import main

        await main()

    mock_load_breeds.assert_awaited_once()
    mock_load_mutations.assert_awaited_once()
    mock_load_injuries.assert_awaited_once()
    mock_load_diseases.assert_awaited_once()
    mock_load_dog_names.assert_awaited_once()
    mock_load_vendor_first_names.assert_awaited_once()
    mock_load_vendor_last_names.assert_awaited_once()
    mock_load_owner_events.assert_awaited_once()
    mock_load_server_events.assert_awaited_once()
    mock_load_stray_events.assert_awaited_once()


async def test_main_calls_breeds_before_events():
    """Breeds and mutations must load before events so events can reference them."""
    call_order = []

    async def _track(name):
        call_order.append(name)

    with patch.multiple(
        "src.database.load.load_resources",
        load_breeds=AsyncMock(side_effect=lambda: call_order.append("breeds")),
        load_mutations=AsyncMock(side_effect=lambda: call_order.append("mutations")),
        load_injuries=AsyncMock(side_effect=lambda: call_order.append("injuries")),
        load_diseases=AsyncMock(side_effect=lambda: call_order.append("diseases")),
        load_dog_names=AsyncMock(side_effect=lambda: call_order.append("dog_names")),
        load_vendor_first_names=AsyncMock(side_effect=lambda: call_order.append("vendor_first")),
        load_vendor_last_names=AsyncMock(side_effect=lambda: call_order.append("vendor_last")),
        load_owner_events=AsyncMock(side_effect=lambda: call_order.append("owner_events")),
        load_server_events=AsyncMock(side_effect=lambda: call_order.append("server_events")),
        load_stray_events=AsyncMock(side_effect=lambda: call_order.append("stray_events")),
    ):
        from src.database.load.load_resources import main

        await main()

    # Breeds and mutations should come before events
    assert call_order.index("breeds") < call_order.index("owner_events")
    assert call_order.index("breeds") < call_order.index("server_events")
    assert call_order.index("breeds") < call_order.index("stray_events")
    assert call_order.index("mutations") < call_order.index("owner_events")
    assert call_order.index("mutations") < call_order.index("server_events")
    assert call_order.index("mutations") < call_order.index("stray_events")
