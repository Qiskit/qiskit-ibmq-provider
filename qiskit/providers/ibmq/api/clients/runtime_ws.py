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
from typing import Optional, Any
from ssl import SSLError

from websockets import connect, ConnectionClosed
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import InvalidURI

from ..exceptions import WebsocketError, WebsocketTimeoutError

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
            WebsocketError: If the connection to the websocket server could
                not be established.
            WebsocketAuthenticationError: If the connection to the websocket
                was established, but the authentication failed.
            WebsocketIBMQProtocolError: If the connection to the websocket
                server was established, but the answer was unexpected.
        """
        try:
            logger.debug('Starting new websocket connection: %s', url)
            # TODO: Re-enable ping_timeout when server is fixed.
            websocket = await connect(url, extra_headers=self._header, ping_interval=None)
            await websocket.recv()  # Ack from server

        # Isolate specific exceptions, so they are not retried in `get_job_status`.
        except (SSLError, InvalidURI) as ex:
            raise ex

        # pylint: disable=broad-except
        except Exception as ex:
            exception_to_raise = WebsocketError('Failed to connect to the server.')

            logger.info('An exception occurred. Raising "%s" from "%s"',
                        repr(exception_to_raise), repr(ex))
            raise exception_to_raise from ex

        logger.debug("Runtime websocket connection established.")
        return websocket

    async def job_results(
            self,
            job_id: str,
            timeout: Optional[float] = 5,
            max_retries: int = 5,
            backoff_factor: float = 0.5
    ) -> Any:
        """Return the interim result of a runtime job.

        Args:
            job_id: ID of the job.
            timeout: Timeout value, in seconds.
            max_retries: Max number of retries.
            backoff_factor: Backoff factor used to calculate the
                time to wait between retries.

        Returns:
            The interim result of a job.

        Raises:
            WebsocketError: If the websocket connection ended unexpectedly.
            WebsocketTimeoutError: If the timeout has been reached.
        """
        url = '{}/stream/jobs/{}'.format(self._websocket_url, job_id)

        current_retry = 0

        while current_retry <= max_retries:
            try:
                if self._ws is None:
                    self._ws = await self._connect(url)

                response = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
                return response

            except asyncio.TimeoutError:
                # Timeout during our wait.
                raise WebsocketTimeoutError(
                    'Timeout reached while streaming job results.') from None
            except (WebsocketError, ConnectionClosed) as ex:
                if isinstance(ex, ConnectionClosed):
                    self._ws = None

                logger.debug(
                    f"A websocket error occurred while streaming runtime job result: {str(ex)}")
                current_retry += 1
                if current_retry > max_retries:
                    raise ex

                # Sleep, and then `continue` with retrying.
                backoff_time = self._backoff_time(backoff_factor, current_retry)
                logger.info('Retrying websocket after %s seconds: '
                            'Attempt #%s', backoff_time, current_retry)
                await asyncio.sleep(backoff_time)  # Block asyncio loop for given backoff time.

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
            logger.debug("Closing runtime websocket connection.")
            await self._ws.close()
            self._ws = None
