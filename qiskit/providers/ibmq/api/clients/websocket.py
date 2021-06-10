# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Client for communicating with the IBM Quantum API via websocket."""

import json
import logging
from abc import ABC
from typing import Dict, Any

from websocket import WebSocketApp, STATUS_NORMAL

from qiskit.providers.ibmq.apiconstants import ApiJobStatus, API_JOB_FINAL_STATES
from qiskit.providers.ibmq.utils.utils import filter_data
from ..exceptions import (WebsocketError,
                          WebsocketIBMQProtocolError,
                          WebsocketAuthenticationError)
from ..rest.utils.data_mapper import map_job_status_response
from .base import BaseWebsocketClient, WebsocketClientCloseCode

logger = logging.getLogger(__name__)


class WebsocketMessage(ABC):
    """Container for a message sent or received via websockets."""

    def __init__(self, type_: str, data: Any) -> None:
        """WebsocketMessage constructor.

        Args:
            type_: Message type.
            data: Message data
        """
        self._type = type_
        self._data = data

    @property
    def data(self) -> Any:
        """Return message data."""
        return self._data

    @property
    def type(self) -> str:
        """Return message type."""
        return self._type

    def as_json(self) -> str:
        """Return a JSON representation of the message."""
        return json.dumps({'type': self._type, 'data': self._data})


class WebsocketAuthenticationMessage(WebsocketMessage):
    """Container for an authentication message sent via websockets."""

    def __init__(self, access_token: str) -> None:
        """WebsocketAuthenticationMessage constructor.

        Args:
            access_token: Access token.
        """
        super().__init__(type_='authentication', data=access_token)


class WebsocketResponseMethod(WebsocketMessage):
    """Container for a message received via websockets."""

    @classmethod
    def from_json(cls, json_string: str) -> 'WebsocketResponseMethod':
        """Instantiate a message from a JSON response."""
        try:
            parsed_dict = json.loads(json_string)
        except (ValueError, AttributeError) as ex:
            exception_to_raise = WebsocketIBMQProtocolError(
                'Unable to parse the message received from the server: {!r}'.format(json_string))

            logger.info('An exception occurred. Raising "%s" from "%s"',
                        repr(exception_to_raise), repr(ex))
            raise exception_to_raise from ex

        return cls(parsed_dict['type'], parsed_dict.get('data', None))


class WebsocketClient(BaseWebsocketClient):
    """Client for websocket communication with the IBM Quantum API."""

    _API_STATUS_INTERNAL_ERROR = 4001
    _API_STATUS_JOB_DONE = 4002
    _API_STATUS_JOB_NOT_FOUND = 4003

    def on_open(self, wsa: WebSocketApp) -> None:
        """Called when websocket connection established.

        Args:
            wsa: WebSocketApp object.
        """
        super().on_open(wsa)
        # Authenticate against the server.
        auth_request = WebsocketAuthenticationMessage(access_token=self._access_token)
        self._ws.send(auth_request.as_json())

    def _handle_message(self, message: str) -> None:
        """Handle received message.

        Args:
            message: Message received.
        """
        if not self._authenticated:
            # First message is an auth ACK
            self._handle_auth_response(message)
        else:
            self._handle_status_response(message)

    def _handle_auth_response(self, message: str) -> None:
        """Handle authentication response.

        Args:
            message: Authentication response message.
        """
        auth_response = WebsocketResponseMethod.from_json(message)
        if auth_response.type != "authenticated":
            self._error = message
            self.disconnect(WebsocketClientCloseCode.PROTOCOL_ERROR)
        else:
            self._authenticated = True

    def _handle_status_response(self, message: str) -> None:
        """Handle status response.

        Args:
            message: Status response message.
        """
        response = WebsocketResponseMethod.from_json(message)
        if logger.getEffectiveLevel() is logging.DEBUG:
            logger.debug('Received message from websocket: %s',
                         filter_data(response.data))
        self._last_message = map_job_status_response(response.data)
        if self._message_queue is not None:
            self._message_queue.put(self._last_message)
        self._current_retry = 0

        job_status = response.data.get('status')
        if job_status and ApiJobStatus(job_status) in API_JOB_FINAL_STATES:
            self.disconnect()

    def get_job_status(
            self,
            retries: int = 5,
            backoff_factor: float = 0.5
    ) -> Dict[str, str]:
        """Return the status of a job.

        Read status messages from the server, which are issued at regular
        intervals. When a final state is reached, the server
        closes the socket. If the websocket connection is closed without
        a reason, the exponential backoff algorithm is used as a basis to
        re-establish the connection. The steps are:

            1. When a connection closes, sleep for a calculated backoff
               time.
            2. Try to make a new connection and increment the retry
               counter.
            3. Attempt to get the job status.

                - If the connection is closed, go back to step 1.
                - If the job status is read successfully, reset the retry
                  counter.

            4. Continue until the job reaches a final state or the maximum
               number of retries is met.

        Args:
            retries: Max number of retries.
            backoff_factor: Backoff factor used to calculate the
                time to wait between retries.

        Returns:
            The final API response for the status of the job, as a dictionary that
            contains at least the keys ``status`` and ``id``.

        Raises:
            WebsocketError: If the websocket connection ended unexpectedly.
            WebsocketTimeoutError: If the timeout has been reached.
        """
        url = '{}/jobs/{}/status/v/1'.format(self._websocket_url, self._job_id)
        return self.stream(url=url, retries=retries, backoff_factor=backoff_factor)

    def _handle_stream_iteration(self) -> None:
        """Handle a streaming iteration."""
        if not self._authenticated:
            raise WebsocketAuthenticationError(
                f"Failed to authenticate against the server: {self._error}")

        if self._server_close_code == self._API_STATUS_JOB_DONE:
            self._server_close_code = STATUS_NORMAL

        if self._server_close_code == self._API_STATUS_JOB_NOT_FOUND:
            raise WebsocketError(
                f"Connection with websocket closed with code {self._server_close_code}: "
                f"Job ID {self._job_id} not found.")
