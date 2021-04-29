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

"""Client for accessing IBM Quantum runtime service."""

import logging
import asyncio
from typing import Any
from ssl import SSLError
import queue
import traceback

from websockets import connect, ConnectionClosed
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import InvalidURI

from ..exceptions import WebsocketError, WebsocketRetryableError

logger = logging.getLogger(__name__)


class RuntimeWebsocketClient:
    """Client for websocket communication with the IBM Quantum runtime service."""

    BACKOFF_MAX = 8
    """Maximum time to wait between retries."""

    def __init__(
            self,
            websocket_url: str,
            access_token: str
    ) -> None:
        """WebsocketClient constructor.

        Args:
            websocket_url: URL for websocket communication with runtime service.
            access_token: Access token for IBM Quantum Experience.
        """
        self._websocket_url = websocket_url.rstrip('/')
        self._access_token = access_token
        self._header = {"X-Access-Token": self._access_token}
        self._ws = None

    async def _connect(self, url: str) -> WebSocketClientProtocol:
        """Authenticate with the websocket server and return the connection.

        Returns:
            An open websocket connection.

        Raises:
            WebsocketRetryableError: If the connection to the websocket server could
                not be established.
        """
        try:
            logger.debug('Starting new websocket connection: %s', url)
            websocket = await connect(url, extra_headers=self._header)
            await websocket.recv()  # Ack from server

        # Isolate specific exceptions, so they are not retried.
        except (SSLError, InvalidURI) as ex:
            raise ex

        # pylint: disable=broad-except
        except Exception as ex:
            exception_to_raise = WebsocketRetryableError('Failed to connect to the server.')
            raise exception_to_raise from ex

        logger.debug("Runtime websocket connection established.")
        return websocket

    async def job_results(
            self,
            job_id: str,
            result_queue: queue.Queue,
            max_retries: int = 5,
            backoff_factor: float = 0.5
    ) -> Any:
        """Return the interim result of a runtime job.

        Args:
            job_id: ID of the job.
            result_queue: Queue used to hold response received from the server.
            max_retries: Max number of retries.
            backoff_factor: Backoff factor used to calculate the
                time to wait between retries.

        Returns:
            The interim result of a job.

        Raises:
            WebsocketError: If a websocket error occurred.
            WebsocketRetryableError: If a websocket error occurred and maximum retry reached.
        """
        url = '{}/stream/jobs/{}'.format(self._websocket_url, job_id)

        current_retry = 0

        while current_retry <= max_retries:
            try:
                if self._ws is None:
                    self._ws = await self._connect(url)
                while True:
                    try:
                        response = await self._ws.recv()
                        result_queue.put_nowait(response)
                        current_retry = 0  # Reset counter after a good receive.
                    except ConnectionClosed as ex:
                        if ex.code == 1000:  # Job has finished.
                            return
                        exception_to_raise = WebsocketRetryableError(
                            f"Connection with websocket for job {job_id} "
                            f"closed unexpectedly: {ex.code}")
                        raise exception_to_raise

            except asyncio.CancelledError:
                logger.debug("Streaming is cancelled.")
                return
            except WebsocketRetryableError as ex:
                logger.debug("A websocket error occurred while streaming "
                             "results for runtime job %s:\n%s", job_id, traceback.format_exc())
                current_retry += 1
                if current_retry > max_retries:
                    raise ex

                backoff_time = self._backoff_time(backoff_factor, current_retry)
                logger.info("Retrying websocket after %s seconds. Attemp %s",
                            backoff_time, current_retry)
                await asyncio.sleep(backoff_time)  # Block asyncio loop for given backoff time.
                continue  # Continues next iteration after `finally` block.
            finally:
                await self.disconnect()

        # Execution should not reach here, sanity check.
        exception_message = 'Max retries exceeded: Failed to establish a websocket ' \
                            'connection due to a network error.'
        raise WebsocketError(exception_message)

    def _backoff_time(self, backoff_factor: float, current_retry_attempt: int) -> float:
        """Calculate the backoff time to wait for.

        Exponential backoff time formula::
            {backoff_factor} * (2 ** (current_retry_attempt - 1))

        Args:
            backoff_factor: Backoff factor, in seconds.
            current_retry_attempt: Current number of retry attempts.

        Returns:
            The number of seconds to wait for, before making the next retry attempt.
        """
        backoff_time = backoff_factor * (2 ** (current_retry_attempt - 1))
        return min(self.BACKOFF_MAX, backoff_time)

    async def disconnect(self) -> None:
        """Close the websocket connection."""
        if self._ws is not None:
            logger.debug("Closing runtime websocket connection.")  # type: ignore[unreachable]
            await self._ws.close()
            self._ws = None
