import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class AsyncBridge:
    """
    A bridge for running async code from synchronous Flask routes.

    Maintains a single event loop running in a background thread,
    which allows async database connections to persist across requests.
    """

    _instance: "AsyncBridge | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    @classmethod
    def get_instance(cls) -> "AsyncBridge":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._start()
        return cls._instance

    def _start(self) -> None:
        """Start the background event loop thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait(timeout=5.0)  # Wait for loop to be ready

    def _run_loop(self) -> None:
        """Run the event loop in the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Run an async coroutine and return its result.

        This method is thread-safe and can be called from any thread.

        Parameters
        ----------
        coro : Coroutine
            The coroutine to run.

        Returns
        -------
        T
            The result of the coroutine.

        Raises
        ------
        Exception
            Any exception raised by the coroutine.
        """
        if self._loop is None:
            raise RuntimeError("Event loop not initialized")

        # Submit the coroutine to the event loop and wait for the result
        future: Future[T] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def shutdown(self) -> None:
        """Shutdown the event loop and background thread."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._loop = None
        self._thread = None
        self._started.clear()


# Convenience function for running async code
def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine from synchronous code.

    This is the main entry point for calling async functions from Flask routes.

    Example
    -------
    ```python
    @app.route('/api/kennels')
    def get_kennels():
        kennels = run_async(list_owner_kennels(discord_id))
        return jsonify([k.to_dict() for k in kennels])
    ```

    Parameters
    ----------
    coro : Coroutine
        The coroutine to run.

    Returns
    -------
    T
        The result of the coroutine.
    """
    bridge = AsyncBridge.get_instance()
    return bridge.run(coro)
