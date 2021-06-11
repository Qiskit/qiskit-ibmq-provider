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
# pylint: disable=unused-argument

"""Base clients for accessing IBM Quantum."""

import logging
from typing import Optional, Any, Dict
from queue import Queue
from abc import ABC
from abc import abstractmethod
import traceback
import time
import enum

from websocket import WebSocketApp, STATUS_NORMAL, STATUS_ABNORMAL_CLOSED

from ...credentials import Credentials
from ..exceptions import WebsocketError, WebsocketTimeoutError
from .utils import ws_proxy_params

logger = logging.getLogger(__name__)


class BaseClient:
    """Abstract class for clients."""
    pass


class WebsocketClientCloseCode(enum.IntEnum):
    """Possible values used for closing websocket connection."""

    NORMAL = 1
    TIMEOUT = 2
    PROTOCOL_ERROR = 3
    CANCEL = 4


class BaseWebsocketClient(BaseClient, ABC):
    """Base class for websocket clients."""

    BACKOFF_MAX = 8
    """Maximum time to wait between retries."""

    def __init__(
            self,
            websocket_url: str,
            credentials: Credentials,
            job_id: str,
            message_queue: Optional[Queue] = None
    ) -> None:
        """BaseWebsocketClient constructor.

        Args:
            websocket_url: URL for websocket communication with IBM Quantum Experience.
            credentials: Account credentials.
            job_id: Job ID.
            message_queue: Queue used to hold received messages.
        """
        self._websocket_url = websocket_url.rstrip('/')
        self._proxy_params = ws_proxy_params(credentials=credentials, ws_url=self._websocket_url)
        self._access_token = credentials.access_token
        self._job_id = job_id
        self._message_queue = message_queue
        self._header: Optional[Dict] = None
        self._ws: Optional[WebSocketApp] = None

        self._authenticated = False
        self._cancelled = False
        self.connected = False
        self._last_message: Any = None
        self._current_retry = 0
        self._server_close_code = STATUS_ABNORMAL_CLOSED
        self._client_close_code = None
        self._error: Optional[str] = None

    def on_open(self, wsa: WebSocketApp) -> None:
        """Called when websocket connection established.

        Args:
            wsa: WebSocketApp object.
        """
        logger.debug("Websocket connection established for job %s", self._job_id)
        self.connected = True
        if self._cancelled:
            # Immediately disconnect if pre-cancelled.
            self.disconnect(WebsocketClientCloseCode.CANCEL)

    def on_message(self, wsa: WebSocketApp, message: str) -> None:
        """Called when websocket message received.

        Args:
            wsa: WebSocketApp object.
            message: Message received.
        """
        try:
            self._handle_message(message)
        except Exception as err:  # pylint: disable=broad-except
            self._error = self._format_exception(err)
            self.disconnect(WebsocketClientCloseCode.PROTOCOL_ERROR)

    @abstractmethod
    def _handle_message(self, message: str) -> None:
        """Handle received message.

        Args:
            message: Message received.
        """
        pass

    def on_close(self, wsa: WebSocketApp, status_code: int, msg: str) -> None:
        """Called when websocket connection clsed.

        Args:
            wsa: WebSocketApp object.
            status_code: Status code.
            msg: Close message.
        """
        # Assume abnormal close if no code is given.
        self._server_close_code = status_code or STATUS_ABNORMAL_CLOSED
        self.connected = False
        logger.debug("Websocket connection for job %s closed. status code=%s, message=%s",
                     self._job_id, status_code, msg)

    def on_error(self, wsa: WebSocketApp, error: Exception) -> None:
        """Called when a websocket error occurred.

        Args:
            wsa: WebSocketApp object.
            error: Encountered error.
        """
        self._error = self._format_exception(error)

    def stream(
            self,
            url: str,
            retries: int = 5,
            backoff_factor: float = 0.5,
    ) -> Any:
        """Stream from the websocket.

        Args:
            url: Websocket url to use.
            retries: Max number of retries.
            backoff_factor: Backoff factor used to calculate the
                time to wait between retries.

        Returns:
            The final message received.

        Raises:
            WebsocketError: If the websocket connection ended unexpectedly.
            WebsocketTimeoutError: If the operation timed out.
        """
        self._reset_state()
        self._cancelled = False

        while self._current_retry <= retries:
            self._ws = WebSocketApp(url,
                                    header=self._header,
                                    on_open=self.on_open,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)
            try:
                logger.debug('Starting new websocket connection: %s using proxy %s',
                             url, self._proxy_params)
                self._reset_state()
                self._ws.run_forever(**self._proxy_params)
                self.connected = False

                logger.debug("Websocket run_forever finished.")

                # Handle path-specific errors
                self._handle_stream_iteration()

                if self._client_close_code in (WebsocketClientCloseCode.NORMAL,
                                               WebsocketClientCloseCode.CANCEL):
                    # If we closed the connection with a normal code.
                    return self._last_message

                if self._client_close_code == WebsocketClientCloseCode.TIMEOUT:
                    raise WebsocketTimeoutError(
                        'Timeout reached while getting job status.') from None

                if self._server_close_code == STATUS_NORMAL and self._error is None:
                    return self._last_message

                msg_to_log = f"A websocket error occurred while streaming for job " \
                             f"{self._job_id}. Connection closed with {self._server_close_code}."
                if self._error is not None:
                    msg_to_log += f"\n{self._error}"
                logger.info(msg_to_log)

                self._current_retry += 1
                if self._current_retry > retries:
                    error_message = "Max retries exceeded: Failed to establish a " \
                                    f"websocket connection."
                    if self._error:
                        error_message += f" Error: {self._error}"

                    raise WebsocketError(error_message)
            finally:
                self.disconnect(None)

            # Sleep then retry.
            backoff_time = self._backoff_time(backoff_factor, self._current_retry)
            logger.info('Retrying get_job_status via websocket after %s seconds: '
                        'Attempt #%s', backoff_time, self._current_retry)
            time.sleep(backoff_time)

        # Execution should not reach here, sanity check.
        exception_message = 'Max retries exceeded: Failed to establish a websocket ' \
                            'connection due to a network error.'

        logger.info(exception_message)
        raise WebsocketError(exception_message)

    @abstractmethod
    def _handle_stream_iteration(self) -> None:
        """Called at the end of an iteration."""
        pass

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

    def disconnect(
            self,
            close_code: Optional[WebsocketClientCloseCode] = WebsocketClientCloseCode.NORMAL
    ) -> None:
        """Close the websocket connection.

        Args:
            close_code: Disconnect status code.
        """
        if self._ws is not None:
            logger.debug("Client closing websocket connection with code %s.", close_code)
            self._client_close_code = close_code
            self._ws.close()
        if close_code == WebsocketClientCloseCode.CANCEL:
            self._cancelled = True

    def _format_exception(self, error: Exception) -> str:
        """Format the exception.

        Args:
            error: Exception to be formatted.

        Returns:
            Formatted exception.
        """
        return "".join(traceback.format_exception(
            type(error), error, getattr(error, '__traceback__', "")))

    def _reset_state(self) -> None:
        """Reset state for a new connection."""
        self._authenticated = False
        self.connected = False
        self._error = None
        self._server_close_code = None
        self._client_close_code = None
