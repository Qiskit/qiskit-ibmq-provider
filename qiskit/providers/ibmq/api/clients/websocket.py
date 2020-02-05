# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Client for websocket communication with the IBM Q Experience API."""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Union, Generator, Optional, Any
from concurrent import futures
from ssl import SSLError
import warnings
from collections import deque

import nest_asyncio
from websockets import connect, ConnectionClosed
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import InvalidURI

from qiskit.providers.ibmq.apiconstants import ApiJobStatus, API_JOB_FINAL_STATES
from ..exceptions import (WebsocketError, WebsocketTimeoutError,
                          WebsocketIBMQProtocolError,
                          WebsocketAuthenticationError)

from .base import BaseClient


logger = logging.getLogger(__name__)

# `asyncio` by design does not allow event loops to be nested. Jupyter (really
# tornado) has its own event loop already so we need to patch it.
# Patch asyncio to allow nested use of `loop.run_until_complete()`.
nest_asyncio.apply()

# TODO Replace coroutine with async def once Python 3.5 is dropped.
# Also can upgrade to websocket 8 to avoid other deprecation warning.
warnings.filterwarnings("ignore", category=DeprecationWarning,
                        message="\"@coroutine\" decorator is deprecated")


class WebsocketMessage(ABC):
    """Container for a message sent or received via websockets.

    Args:
        type_: message type.
    """
    def __init__(self, type_: str) -> None:
        self.type_ = type_

    @abstractmethod
    def get_data(self) -> Union[str, Dict[str, str]]:
        """Getter for "abstract" attribute subclasses define, `data`."""
        pass

    def as_json(self) -> str:
        """Return a json representation of the message."""
        return json.dumps({'type': self.type_, 'data': self.get_data()})


class WebsocketAuthenticationMessage(WebsocketMessage):
    """Container for an authentication message sent via websockets.

    Args:
        type_: message type.
        data: data type.
    """
    def __init__(self, type_: str, data: str) -> None:
        super().__init__(type_)
        self.data = data

    def get_data(self) -> str:
        return self.data


class WebsocketResponseMethod(WebsocketMessage):
    """Container for a message received via websockets.

    Args:
        type_: message type.
        data: data type.
    """
    def __init__(self, type_: str, data: Dict[str, str]) -> None:
        super().__init__(type_)
        self.data = data

    def get_data(self) -> Dict[str, str]:
        return self.data

    @classmethod
    def from_bytes(cls, json_string: bytes) -> 'WebsocketResponseMethod':
        """Instantiate a message from a bytes response."""
        try:
            parsed_dict = json.loads(json_string.decode('utf8'))
        except (ValueError, AttributeError) as ex:
            raise WebsocketIBMQProtocolError('Unable to parse message') from ex

        return cls(parsed_dict['type'], parsed_dict.get('data', None))


class WebsocketClient(BaseClient):
    """Client for websocket communication with the IBM Q Experience API.

    Args:
        websocket_url: URL for websocket communication with IBM Q.
        access_token: access token for IBM Q.
    """
    BACKOFF_MAX = 8  # Maximum time to wait between retries.

    def __init__(self, websocket_url: str, access_token: str) -> None:
        self.websocket_url = websocket_url.rstrip('/')
        self.access_token = access_token

    @asyncio.coroutine
    def _connect(self, url: str) -> Generator[Any, None, WebSocketClientProtocol]:
        """Authenticate against the websocket server, returning the connection.

        Returns:
            an open websocket connection.

        Raises:
            WebsocketError: if the connection to the websocket server could
                not be established.
            WebsocketAuthenticationError: if the connection to the websocket
                was established, but the authentication failed.
            WebsocketIBMQProtocolError: if the connection to the websocket
                server was established, but the answer was unexpected.
        """
        try:
            logger.debug('Starting new websocket connection: %s', url)
            with warnings.catch_warnings():
                # Suppress websockets deprecation warnings until the fix is available
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                websocket = yield from connect(url)

        # Isolate specific exceptions, so they are not retried in `get_job_status`.
        except (SSLError, InvalidURI) as ex:
            raise ex

        # pylint: disable=broad-except
        except Exception as ex:
            raise WebsocketError('Could not connect to server') from ex

        try:
            # Authenticate against the server.
            auth_request = self._authentication_message()
            with warnings.catch_warnings():
                # Suppress websockets deprecation warnings until the fix is available
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                yield from websocket.send(auth_request.as_json())

                # Verify that the server acknowledged our authentication.
                auth_response_raw = yield from websocket.recv()

            auth_response = WebsocketResponseMethod.from_bytes(auth_response_raw)

            if auth_response.type_ != 'authenticated':
                raise WebsocketIBMQProtocolError(auth_response.as_json())
        except ConnectionClosed as ex:
            yield from websocket.close()
            raise WebsocketAuthenticationError(
                'Error during websocket authentication') from ex

        return websocket

    @asyncio.coroutine
    def get_job_status(
            self,
            job_id: str,
            timeout: Optional[float] = None,
            retries: int = 5,
            backoff_factor: float = 0.5,
            status_deque: Optional[deque] = None
    ) -> Generator[Any, None, Dict[str, str]]:
        """Return the status of a job.

        Reads status messages from the API, which are issued at regular
        intervals. When a final state is reached, the server
        closes the socket. If the websocket connection is closed without
        a reason, the exponential backoff algorithm is used as a basis to
        reestablish connections. The algorithm takes effect when a
        connection closes, it is given by:

            1. When a connection closes, sleep for a calculated backoff
                time.
            2. Try to retrieve another socket and increment a retry
                counter.
            3. Attempt to get the job status.
                - If the connection is closed, go back to step 1.
                - If the job status is read successfully, reset the retry
                    counter.
            4. Continue until the job status is complete or the maximum
                number of retries is met.

        Args:
            job_id: id of the job.
            timeout: timeout, in seconds.
            retries: max number of retries.
            backoff_factor: backoff factor used to calculate the
                time to wait between retries.
            status_deque: deque used to share the latest status.

        Returns:
            the API response for the status of a job, as a dict that
                contains at least the keys ``status`` and ``id``.

        Raises:
            WebsocketError: if the websocket connection ended unexpectedly.
            WebsocketTimeoutError: if the timeout has been reached.
        """
        url = '{}/jobs/{}/status'.format(self.websocket_url, job_id)

        original_timeout = timeout
        start_time = time.time()
        attempt_retry = True  # By default, attempt to retry if the websocket connection closes.
        current_retry_attempt = 0
        last_status = None
        websocket = None

        while current_retry_attempt <= retries:
            try:
                websocket = yield from self._connect(url)
                # Read messages from the server until the connection is closed or
                # a timeout has been reached.
                while True:
                    try:
                        with warnings.catch_warnings():
                            # Suppress websockets deprecation warnings until the fix is available
                            warnings.filterwarnings("ignore", category=DeprecationWarning)
                            if timeout:
                                response_raw = yield from asyncio.wait_for(
                                    websocket.recv(), timeout=timeout)

                                # Decrease the timeout.
                                timeout = original_timeout - (time.time() - start_time)
                            else:
                                response_raw = yield from websocket.recv()
                        logger.debug('Received message from websocket: %s',
                                     response_raw)

                        response = WebsocketResponseMethod.from_bytes(response_raw)
                        last_status = response.data

                        # Successfully received and parsed a message, reset retry counter.
                        current_retry_attempt = 0

                        job_status = response.data.get('status')
                        if (job_status and
                                ApiJobStatus(job_status) in API_JOB_FINAL_STATES):
                            return last_status

                        if timeout and timeout <= 0:
                            raise WebsocketTimeoutError('Timeout reached')

                        # Share the new status.
                        if status_deque is not None:
                            status_deque.append(last_status)

                    except (futures.TimeoutError, asyncio.TimeoutError):
                        # Timeout during our wait.
                        raise WebsocketTimeoutError('Timeout reached') from None
                    except ConnectionClosed as ex:
                        # From the API:
                        # 4001: closed due to an internal errors
                        # 4002: closed on purpose (no more updates to send)
                        # 4003: closed due to job not found.
                        message = 'Unexpected error'
                        if ex.code == 4001:
                            message = 'Internal server error'
                        elif ex.code == 4002:
                            return last_status  # type: ignore[return-value]
                        elif ex.code == 4003:
                            attempt_retry = False  # No point in retrying.
                            message = 'Job id not found'

                        raise WebsocketError('Connection with websocket closed '
                                             'unexpectedly: {}(status_code={})'
                                             .format(message, ex.code)) from ex

            except WebsocketError as ex:
                logger.info('A websocket error occurred: %s', ex)

                # Specific `WebsocketError` exceptions that are not worth retrying.
                if isinstance(ex, (WebsocketTimeoutError, WebsocketIBMQProtocolError)):
                    raise ex

                current_retry_attempt = current_retry_attempt + 1
                if (current_retry_attempt > retries) or (not attempt_retry):
                    raise ex

                # Sleep, and then `continue` with retrying.
                backoff_time = self._backoff_time(backoff_factor, current_retry_attempt)
                logger.info('Retrying get_job_status via websocket after %s seconds: '
                            'Attempt #%s.', backoff_time, current_retry_attempt)
                yield from asyncio.sleep(backoff_time)  # Block asyncio loop for given backoff time.

                continue  # Continues next iteration after `finally` block.

            finally:
                with warnings.catch_warnings():
                    # Suppress websockets deprecation warnings until the fix is available
                    warnings.filterwarnings("ignore", category=DeprecationWarning)
                    if websocket is not None:
                        yield from websocket.close()

        # Execution should not reach here, sanity check.
        raise WebsocketError('Failed to establish a websocket '
                             'connection after {} retries.'.format(retries))

    def _backoff_time(self, backoff_factor: float, current_retry_attempt: int) -> float:
        """Calculate the backoff time to sleep for.

        Exponential backoff time formula:
                {backoff_factor} * (2 ** (current_retry_attempt - 1))

        Args:
            backoff_factor: backoff factor, in seconds.
            current_retry_attempt: current number of retry attempts.

        Returns:
            The number of seconds to sleep for, before a retry attempt is made.
        """
        backoff_time = backoff_factor * (2 ** (current_retry_attempt - 1))
        return min(self.BACKOFF_MAX, backoff_time)

    def _authentication_message(self) -> 'WebsocketAuthenticationMessage':
        """Return the message used for authenticating against the server."""
        return WebsocketAuthenticationMessage(type_='authentication',
                                              data=self.access_token)
