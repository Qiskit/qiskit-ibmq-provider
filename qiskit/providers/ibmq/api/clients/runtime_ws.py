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
# pylint: disable=unused-argument

"""Client for accessing IBM Quantum runtime service."""

import logging
import time
from typing import Any, Dict, Optional
import queue
import traceback
from urllib.parse import urlparse

from websocket import WebSocketApp

from ...credentials import Credentials
from ..exceptions import WebsocketError

logger = logging.getLogger(__name__)


class RuntimeWebsocketClient:
    """Client for websocket communication with the IBM Quantum runtime service."""

    BACKOFF_MAX = 8
    """Maximum time to wait between retries."""

    def __init__(
            self,
            credentials: Credentials,
            job_id: str
    ) -> None:
        """WebsocketClient constructor.

        Args:
            credentials: Account credentials.
            job_id: ID of the job.
        """
        self._ws_url = credentials.runtime_url.replace('https', 'wss').rstrip('/')
        self._header = {"X-Access-Token": credentials.access_token}
        self._proxy_params = self._get_proxy_params(credentials)
        self._ws = None
        self._connect_ack = False
        self._job_id = job_id
        self._result_queue = None  # type: Optional[queue.Queue]
        self._normal_close = False
        self._current_retry = 0

    def on_open(self, wsa: WebSocketApp) -> None:
        """Called when websocket connection established.

        Args:
            wsa: WebSocketApp object.
        """
        logger.debug("Runtime websocket connection established for job %s", self._job_id)

    def on_message(self, wsa: WebSocketApp, message: str) -> None:
        """Called when websocket message received.

        Args:
            wsa: WebSocketApp object.
            message: Message received.
        """
        if not self._connect_ack:
            self._connect_ack = True
        else:
            self._result_queue.put_nowait(message)
            self._current_retry = 0

    def on_close(self, wsa: WebSocketApp, status_code: int, msg: str) -> None:
        """Called when websocket connection clsed.

        Args:
            wsa: WebSocketApp object.
            status_code: Status code.
            msg: Close message.
        """
        if status_code == 1000:
            logger.debug("Websocket connection for job %s closed.", self._job_id)
            self._normal_close = True
        else:
            logger.info("Websocket connection closed unexpectedly while streaming "
                        "results for runtime job %s: status code=%s, message=%s",
                        self._job_id, status_code, msg)

    def on_error(self, wsa: WebSocketApp, error: Exception) -> None:
        """Called when a websocket error occurred.

        Args:
            wsa: WebSocketApp object.
            error: Encountered error.
        """
        logger.info(
            "A websocket error occurred while streaming results for runtime job %s:\n%s",
            self._job_id, "".join(traceback.format_exception(
                type(error), error, getattr(error, '__traceback__', ""))))

    def job_results(
            self,
            result_queue: queue.Queue,
            max_retries: int = 5,
            backoff_factor: float = 0.5
    ) -> Any:
        """Return the interim result of a runtime job.

        Args:
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
        self._result_queue = result_queue
        url = '{}/stream/jobs/{}'.format(self._ws_url, self._job_id)

        while self._current_retry <= max_retries:
            self._connect_ack = False
            self._ws = WebSocketApp(url,
                                    header=self._header,
                                    on_open=self.on_open,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)
            try:
                logger.debug('Starting new websocket connection: %s using proxy %s',
                             url, self._proxy_params)
                self._ws.run_forever(**self._proxy_params)

                if self._normal_close:
                    return

                self._current_retry += 1
                if self._current_retry > max_retries:
                    raise WebsocketError(f"A websocket error occurred while streaming "
                                         f"results for runtime job {self._job_id}")
            finally:
                self.disconnect()

            backoff_time = self._backoff_time(backoff_factor, self._current_retry)
            logger.info("Retrying websocket after %s seconds. Attemp %s",
                        backoff_time, self._current_retry)
            time.sleep(backoff_time)

        # Execution should not reach here, sanity check.
        exception_message = 'Max retries exceeded: Failed to establish a websocket ' \
                            'connection due to a network error.'
        raise WebsocketError(exception_message)

    def _get_proxy_params(self, credentials: Credentials) -> Dict:
        """Extract proxy information.

        Returns:
            Proxy information to be used by the websocket client.
        """
        conn_data = credentials.connection_parameters()
        out = {}

        if "proxies" in conn_data:
            proxies = conn_data['proxies']
            url_parts = urlparse(self._ws_url)
            proxy_keys = [
                self._ws_url,
                'wss',
                'https://' + url_parts.hostname,
                'https',
                'all://' + url_parts.hostname,
                'all'
                ]
            for key in proxy_keys:
                if key in proxies:
                    proxy_parts = urlparse(proxies[key], scheme="http")
                    out['http_proxy_host'] = proxy_parts.hostname
                    out['http_proxy_port'] = proxy_parts.port
                    out['proxy_type'] = \
                        "http" if proxy_parts.scheme.startswith("http") else proxy_parts.scheme
                    if proxy_parts.username and proxy_parts.password:
                        out['http_proxy_auth'] = (proxy_parts.username, proxy_parts.password)
                    break

        if "auth" in conn_data:
            out['http_proxy_auth'] = (credentials.proxies['username_ntlm'],
                                      credentials.proxies['password_ntlm'])

        return out

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

    def disconnect(self, normal: bool = False) -> None:
        """Close the websocket connection.

        Args:
            normal: Whether it's a normal disconnect.
        """
        if self._ws is not None:
            logger.debug("Closing runtime websocket connection.")  # type: ignore[unreachable]
            self._normal_close = normal
            self._ws.close()
            self._ws = None
