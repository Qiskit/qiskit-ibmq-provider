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
from concurrent import futures
import warnings

import nest_asyncio
from websockets import connect, ConnectionClosed

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


class WebsocketMessage:
    """Container for a message sent or received via websockets.

    Attributes:
        type_ (str): message type.
        data (dict): message data.
    """
    def __init__(self, type_, data=None):
        self.type_ = type_
        self.data = data

    def as_json(self):
        """Return a json representation of the message."""
        parsed_dict = {'type': self.type_}
        if self.data:
            parsed_dict['data'] = self.data
        return json.dumps(parsed_dict)

    @classmethod
    def from_bytes(cls, json_string):
        """Instantiate a message from a bytes response."""
        try:
            parsed_dict = json.loads(json_string.decode('utf8'))
        except (ValueError, AttributeError) as ex:
            raise WebsocketIBMQProtocolError('Unable to parse message') from ex

        return cls(parsed_dict['type'], parsed_dict.get('data', None))


class WebsocketClient(BaseClient):
    """Client for websocket communication with the IBM Q Experience API.

    Attributes:
        websocket_url (str): URL for websocket communication with IBM Q.
        access_token (str): access token for IBM Q.
    """

    def __init__(self, websocket_url, access_token):
        self.websocket_url = websocket_url.rstrip('/')
        self.access_token = access_token

    @asyncio.coroutine
    def _connect(self, url):
        """Authenticate against the websocket server, returning the connection.

        Returns:
            Connect: an open websocket connection.

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

            auth_response = WebsocketMessage.from_bytes(auth_response_raw)

            if auth_response.type_ != 'authenticated':
                raise WebsocketIBMQProtocolError(auth_response.as_json())
        except ConnectionClosed as ex:
            yield from websocket.close()
            raise WebsocketAuthenticationError(
                'Error during websocket authentication') from ex

        return websocket

    @asyncio.coroutine
    def get_job_status(self, job_id, timeout=None):
        """Return the status of a job.

        Reads status messages from the API, which are issued at regular
        intervals (20 seconds). When a final state is reached, the server
        closes the socket.

        Args:
            job_id (str): id of the job.
            timeout (int): timeout, in seconds.

        Returns:
            dict: the API response for the status of a job, as a dict that
                contains at least the keys ``status`` and ``id``.

        Raises:
            WebsocketError: if the websocket connection ended unexpectedly.
            WebsocketTimeoutError: if the timeout has been reached.
        """
        url = '{}/jobs/{}/status'.format(self.websocket_url, job_id)
        websocket = yield from self._connect(url)

        original_timeout = timeout
        start_time = time.time()
        last_status = None

        try:
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

                            # Decrease the timeout, with a 5-second grace period.
                            elapsed_time = time.time() - start_time
                            timeout = max(5, int(original_timeout - elapsed_time))
                        else:
                            response_raw = yield from websocket.recv()
                    logger.debug('Received message from websocket: %s',
                                 response_raw)

                    response = WebsocketMessage.from_bytes(response_raw)
                    last_status = response.data

                    job_status = response.data.get('status')
                    if (job_status and
                            ApiJobStatus(job_status) in API_JOB_FINAL_STATES):
                        break

                except futures.TimeoutError:
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
                        break
                    elif ex.code == 4003:
                        message = 'Job id not found'
                    raise WebsocketError('Connection with websocket closed '
                                         'unexpectedly: {}'.format(message)) from ex
        finally:
            with warnings.catch_warnings():
                # Suppress websockets deprecation warnings until the fix is available
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                yield from websocket.close()

        return last_status

    def _authentication_message(self):
        """Return the message used for authenticating against the server."""
        return WebsocketMessage(type_='authentication',
                                data=self.access_token)
