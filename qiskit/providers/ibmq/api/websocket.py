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

"""Utilities for IBM Q API connector."""

import asyncio
import json
import time
from concurrent import futures

import websockets

from .exceptions import WebsocketError, WebsocketTimeoutError


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
        parsed_dict = json.loads(json_string.decode('utf8'))
        return cls(parsed_dict['type'], parsed_dict.get('data', None))


class WebsocketClient:
    """Client for websocket communication with the IBMQ API.

    Attributes:
        websocket_url (str): URL for websocket communication with IBM Q.
        access_token (str): access token for IBMQ.
    """

    def __init__(self, websocket_url, access_token):
        self.websocket_url = websocket_url
        self.access_token = access_token

    @asyncio.coroutine
    def connect(self, url):
        """Authenticate against the websocket server, returning the connection.

        Returns:
            Connect: an open websocket connection.

        Raises:
            WebsocketError: if the connection to the websocket server failed
                due to connection or authentication errors.
        """
        websocket = yield from websockets.connect(url)

        try:
            # Authenticate against the server.
            auth_request = self._authentication_message()
            yield from websocket.send(auth_request.as_json())

            # Verify that the server acknowledged our authentication.
            auth_response_raw = yield from websocket.recv()
            auth_response = WebsocketMessage.from_bytes(auth_response_raw)

            if auth_response.type_ != 'authenticated':
                raise WebsocketError(auth_response.as_json())
        except websockets.ConnectionClosed as ex:
            yield from websocket.close()
            raise WebsocketError('Error in websocket authentication: %s' % ex)

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
        websocket = yield from self.connect(url)

        original_timeout = timeout
        start_time = time.time()
        last_status = None

        try:
            # Read messages from the server until the connection is closed or
            # a timeout has been reached.
            while True:
                try:
                    if timeout:
                        response_raw = yield from asyncio.wait_for(
                            websocket.recv(), timeout=timeout)

                        # Decrease the timeout, with a 5-second grace period.
                        elapsed_time = time.time() - start_time
                        timeout = max(5, int(original_timeout - elapsed_time))
                    else:
                        response_raw = yield from websocket.recv()

                    response = WebsocketMessage.from_bytes(response_raw)
                    last_status = response.data

                except futures.TimeoutError:
                    # Timeout during our wait.
                    raise WebsocketTimeoutError('Timeout reached')
                except websockets.ConnectionClosed as ex:
                    if ex.code == 4002:
                        # 4002 is used by the API to signal closing on purpose.
                        break
                    raise WebsocketError(
                        'Connection with websocket closed: {}'.format(ex))
        finally:
            yield from websocket.close()

        return last_status

    def _authentication_message(self):
        """Return the message used for authenticating agains the server."""
        return WebsocketMessage(type_='authentication',
                                data=self.access_token)
