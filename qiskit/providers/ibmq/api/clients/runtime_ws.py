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
from typing import Optional
from queue import Queue

from ...credentials import Credentials
from .base import BaseWebsocketClient

logger = logging.getLogger(__name__)


class RuntimeWebsocketClient(BaseWebsocketClient):
    """Client for websocket communication with the IBM Quantum runtime service."""

    def __init__(
            self,
            websocket_url: str,
            credentials: Credentials,
            job_id: str,
            message_queue: Optional[Queue] = None
    ) -> None:
        """WebsocketClient constructor.

        Args:
            websocket_url: URL for websocket communication with IBM Quantum.
            credentials: Account credentials.
            job_id: Job ID.
            message_queue: Queue used to hold received messages.
        """
        super().__init__(websocket_url, credentials, job_id, message_queue)
        self._header = {"X-Access-Token": credentials.access_token}

    def _handle_message(self, message: str) -> None:
        """Handle received message.

        Args:
            message: Message received.
        """
        if not self._authenticated:
            self._authenticated = True  # First message is an ACK
        else:
            self._message_queue.put_nowait(message)
            self._current_retry = 0

    def job_results(
            self,
            max_retries: int = 5,
            backoff_factor: float = 0.5
    ) -> None:
        """Return the interim result of a runtime job.

        Args:
            max_retries: Max number of retries.
            backoff_factor: Backoff factor used to calculate the
                time to wait between retries.

        Raises:
            WebsocketError: If a websocket error occurred.
        """
        url = '{}/stream/jobs/{}'.format(self._websocket_url, self._job_id)
        self.stream(url=url, retries=max_retries, backoff_factor=backoff_factor)

    def _handle_stream_iteration(self) -> None:
        """Handle a streaming iteration."""
        pass
