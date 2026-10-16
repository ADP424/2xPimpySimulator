"""Tests for src/web/async_utils.py — the sync→async bridge Flask routes use."""

import threading
from unittest.mock import patch

from src.web.async_utils import AsyncBridge


async def _answer():
    return 42


class TestAsyncBridgeStartup:
    def setup_method(self):
        self._saved = AsyncBridge._instance
        AsyncBridge._instance = None

    def teardown_method(self):
        if AsyncBridge._instance is not None and AsyncBridge._instance is not self._saved:
            AsyncBridge._instance.shutdown()
        AsyncBridge._instance = self._saved

    def test_not_published_until_its_loop_runs(self):
        """A request racing the first one must never get a bridge whose loop isn't running yet."""
        seen_during_start = []
        real_start = AsyncBridge._start

        def start(bridge):
            seen_during_start.append(AsyncBridge._instance)
            real_start(bridge)

        with patch.object(AsyncBridge, "_start", start):
            bridge = AsyncBridge.get_instance()

        assert seen_during_start == [None]
        assert bridge.run(_answer()) == 42

    def test_concurrent_first_requests_all_succeed(self):
        results, errors = [], []

        def request():
            try:
                results.append(AsyncBridge.get_instance().run(_answer()))
            except Exception as error:  # pragma: no cover - the failure being guarded against
                errors.append(error)

        threads = [threading.Thread(target=request) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert results == [42] * 8
