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

"""Test for the Websocket client."""

import asyncio
from contextlib import suppress
import warnings
import sys
import importlib
import threading


import websockets

from qiskit.providers.ibmq.api.exceptions import (
    WebsocketError, WebsocketTimeoutError, WebsocketIBMQProtocolError)
from qiskit.providers.ibmq.api.clients.websocket import WebsocketClient

from ...ibmqtestcase import IBMQTestCase

from .websocket_server import (
    TOKEN_JOB_COMPLETED, TOKEN_JOB_TRANSITION, TOKEN_WRONG_FORMAT,
    TOKEN_TIMEOUT, TOKEN_WEBSOCKET_RETRY_SUCCESS,
    TOKEN_WEBSOCKET_RETRY_FAILURE, TOKEN_WEBSOCKET_JOB_NOT_FOUND,
    websocket_handler)

TEST_IP_ADDRESS = '127.0.0.1'
INVALID_PORT = 9876
VALID_PORT = 8765


class TestWebsocketClient(IBMQTestCase):
    """Tests for the websocket client."""

    def test_invalid_url(self):
        """Test connecting to an invalid URL."""
        client = WebsocketClient('wss://{}:{}'.format(TEST_IP_ADDRESS, INVALID_PORT), None)

        with self.assertRaises(WebsocketError):
            asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))

    def test_asyncio_threading(self):
        """Test asyncio when importing webserver in new thread"""

        def _import_websocket():
            try:
                importlib.reload(sys.modules["qiskit.providers.ibmq.api.clients.websocket"])
            except RuntimeError:
                self.fail("Importing websocket in new thread failed due to asyncio!")

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
        start_server = websockets.serve(websocket_handler, TEST_IP_ADDRESS, int(VALID_PORT))
        cls.server = asyncio.get_event_loop().run_until_complete(start_server)

    @classmethod
    def tearDownClass(cls):
        """Class level cleanup."""
        super().tearDownClass()

        # Close the mock server.
        loop = asyncio.get_event_loop()
        cls.server.close()
        loop.run_until_complete(cls.server.wait_closed())

        with warnings.catch_warnings():
            # Suppress websockets deprecation warning
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            # Manually cancel any pending asyncio tasks.
            pending = asyncio.Task.all_tasks()
        for task in pending:
            task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    loop.run_until_complete(task)
            except Exception as err:  # pylint: disable=broad-except
                cls.log.error("An error %s occurred canceling task %s. "
                              "Traceback:", str(err), str(task))
                task.print_stack()

    def test_job_final_status(self):
        """Test retrieving a job already in final status."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_JOB_COMPLETED)
        response = asyncio.get_event_loop().run_until_complete(
            client.get_job_status('job_id'))
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_job_transition(self):
        """Test retrieving a job that transitions to final status."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_JOB_TRANSITION)
        response = asyncio.get_event_loop().run_until_complete(
            client.get_job_status('job_id'))
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_timeout(self):
        """Test timeout during retrieving a job status."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_TIMEOUT)
        with self.assertRaises(WebsocketTimeoutError):
            _ = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id', timeout=2))

    def test_invalid_response(self):
        """Test unparseable response from the server."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_WRONG_FORMAT)
        with self.assertRaises(WebsocketIBMQProtocolError):
            _ = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))

    def test_websocket_retry_success(self):
        """Test retrieving a job status during a retry attempt."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_WEBSOCKET_RETRY_SUCCESS)
        response = asyncio.get_event_loop().run_until_complete(
            client.get_job_status('job_id'))
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_websocket_retry_failure(self):
        """Test exceeding the retry limit for retrieving a job status."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_WEBSOCKET_RETRY_FAILURE)
        with self.assertRaises(WebsocketError):
            _ = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))

    def test_websocket_job_not_found(self):
        """Test retrieving a job status for an non existent id."""
        client = WebsocketClient('ws://{}:{}'.format(
            TEST_IP_ADDRESS, VALID_PORT), TOKEN_WEBSOCKET_JOB_NOT_FOUND)
        with self.assertRaises(WebsocketError):
            _ = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))
