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

"""Test for the Websocket client."""

import sys
import importlib
import threading

from qiskit.providers.ibmq.api.exceptions import WebsocketError, WebsocketTimeoutError
from qiskit.providers.ibmq.api.clients.websocket import WebsocketClient
from qiskit.providers.ibmq.utils.utils import RefreshQueue
from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.api.clients.account import AccountClient

from ...ibmqtestcase import IBMQTestCase
from ...ws_server import MockWsServer
from .ws_handler import (
    TOKEN_JOB_COMPLETED, TOKEN_JOB_TRANSITION, TOKEN_WRONG_FORMAT,
    TOKEN_TIMEOUT, TOKEN_WEBSOCKET_RETRY_SUCCESS,
    TOKEN_WEBSOCKET_RETRY_FAILURE, TOKEN_WEBSOCKET_JOB_NOT_FOUND,
    websocket_handler)


class TestWebsocketClient(IBMQTestCase):
    """Tests for the websocket client."""

    def test_invalid_url(self):
        """Test connecting to an invalid URL."""
        ws_url = f"wss://{MockWsServer.WS_IP_ADDRESS}:{MockWsServer.WS_INVALID_PORT}"
        cred = Credentials(token="my_token", url="", websockets_url=ws_url)
        client = WebsocketClient(ws_url, cred, "job_id")

        with self.assertRaises(WebsocketError):
            client.get_job_status()

    def test_threading(self):
        """Test when importing webserver in new thread"""

        def _import_websocket():
            try:
                importlib.reload(sys.modules["qiskit.providers.ibmq.api.clients.websocket"])
            except RuntimeError:
                self.fail("Importing websocket in new thread failed!")

        thread = threading.Thread(target=_import_websocket)
        thread.start()
        thread.join()


class TestWebsocketClientMock(IBMQTestCase):
    """Tests for the the websocket client against a mock server."""
    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        super().setUpClass()
        # Launch the mock server.
        cls.server = MockWsServer(websocket_handler, cls.log)
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        """Class level cleanup."""
        super().tearDownClass()
        cls.server.stop()

    def _get_ws_client(self, token=TOKEN_JOB_COMPLETED, url=MockWsServer.VALID_WS_URL):
        cred = Credentials(token="", url="", websockets_url=url,
                           access_token=token)
        return WebsocketClient(url, cred, "job_id")

    def test_job_final_status(self):
        """Test retrieving a job already in final status."""
        client = self._get_ws_client(TOKEN_JOB_COMPLETED)
        response = client.get_job_status()
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_job_transition(self):
        """Test retrieving a job that transitions to final status."""
        client = self._get_ws_client(TOKEN_JOB_TRANSITION)
        response = client.get_job_status()
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_timeout(self):
        """Test timeout during retrieving a job status."""
        cred = Credentials(token="", url="", websockets_url=MockWsServer.VALID_WS_URL,
                           access_token=TOKEN_TIMEOUT)
        account_client = AccountClient(cred)
        with self.assertRaises(WebsocketTimeoutError):
            account_client._job_final_status_websocket("job_id", timeout=2)

    def test_invalid_response(self):
        """Test unparseable response from the server."""
        client = self._get_ws_client(TOKEN_WRONG_FORMAT)
        with self.assertRaises(WebsocketError):
            client.get_job_status()

    def test_websocket_retry_success(self):
        """Test retrieving a job status during a retry attempt."""
        client = self._get_ws_client(TOKEN_WEBSOCKET_RETRY_SUCCESS)
        response = client.get_job_status()
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_websocket_retry_failure(self):
        """Test exceeding the retry limit for retrieving a job status."""
        client = self._get_ws_client(TOKEN_WEBSOCKET_RETRY_FAILURE)
        with self.assertRaises(WebsocketError):
            client.get_job_status()

    def test_websocket_job_not_found(self):
        """Test retrieving a job status for an non existent id."""
        client = self._get_ws_client(TOKEN_WEBSOCKET_JOB_NOT_FOUND)
        with self.assertRaises(WebsocketError):
            client.get_job_status()

    def test_websocket_status_queue(self):
        """Test status queue used by websocket client."""
        status_queue = RefreshQueue(maxsize=10)
        cred = Credentials(token="", url="", websockets_url=MockWsServer.VALID_WS_URL,
                           access_token=TOKEN_JOB_TRANSITION)
        client = WebsocketClient(MockWsServer.VALID_WS_URL, cred, "job_id", status_queue)
        client.get_job_status()
        self.assertEqual(status_queue.qsize(), 2)
