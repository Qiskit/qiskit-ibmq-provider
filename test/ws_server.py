# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Local websocket server for testing."""

import sys
import asyncio
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
import traceback

import websockets


class MockWsServer:
    """Local websocket server for testing."""

    WS_IP_ADDRESS = '127.0.0.1'
    WS_PORT = 8765
    WS_INVALID_PORT = 9876
    VALID_WS_URL = f"ws://{WS_IP_ADDRESS}:{WS_PORT}"

    def __init__(self, handler, logger):
        """Initialize a test server."""
        self._executor = ThreadPoolExecutor()
        self._server_loop = None
        self._handler = handler
        self._ws_future = None
        self._ws_stop_event = None
        self.logger = logger

    def start(self):
        """Start the server."""
        start_event = threading.Event()
        self._ws_future = self._executor.submit(self._server_thread, start_event=start_event)
        start_event.wait(5)
        if not start_event.is_set():
            raise RuntimeError("Unable to start websocket server")

    def stop(self):
        """Stop the server."""
        if not self._ws_future:
            return

        self._server_loop.call_soon_threadsafe(self._ws_stop_event.set)
        self._ws_future.result()

    def _server_thread(self, start_event):
        """Thread to run the websocket server."""
        self._server_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._server_loop)

        self._ws_stop_event = asyncio.Event()

        # pylint: disable=no-member
        start_server = websockets.serve(self._handler, self.WS_IP_ADDRESS, self.WS_PORT)
        server = self._server_loop.run_until_complete(start_server)
        start_event.set()
        self._server_loop.run_until_complete(self._wait_for_stop_event())

        self.logger.debug("Shutting down mock websocket server")

        server.close()
        self._server_loop.run_until_complete(server.wait_closed())

        with warnings.catch_warnings():
            # Suppress websockets deprecation warning
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            # Manually cancel any pending asyncio tasks.
            if sys.version_info[0:2] < (3, 9):
                pending = asyncio.Task.all_tasks()
            else:
                pending = asyncio.all_tasks(self._server_loop)
        for task in pending:
            task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    self._server_loop.run_until_complete(task)
            except Exception as err:  # pylint: disable=broad-except
                self.logger.error(
                    "An error occurred canceling task %s: %s",
                    str(task), "".join(traceback.format_exception(
                        type(err), err, getattr(err, '__traceback__', ""))))

        self.logger.debug("Finish shutting down mock websocket server.")

    async def _wait_for_stop_event(self):
        """Wait for the stop server event."""
        await self._ws_stop_event.wait()
