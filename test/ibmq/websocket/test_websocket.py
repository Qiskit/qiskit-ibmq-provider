# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
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

import websockets

from qiskit.providers.ibmq.api_v2.exceptions import (
    WebsocketError, WebsocketTimeoutError, WebsocketIBMQProtocolError)
from qiskit.providers.ibmq.api_v2.websocket import WebsocketClient
from qiskit.test import QiskitTestCase #, requires_qe_access
#from ..decorators import requires_new_api_auth_credentials


from .websocket_server import (
    TOKEN_JOB_COMPLETED, TOKEN_JOB_TRANSITION, TOKEN_WRONG_FORMAT,
    TOKEN_TIMEOUT, websocket_handler)


class TestWebsocketClient(QiskitTestCase):
    """Tests for the websocket client."""

    def test_invalid_url(self):
        """Test connecting to an invalid URL."""
        client = WebsocketClient('wss://127.0.0.1:9876', None)

        with self.assertRaises(WebsocketError):
            asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))


class TestWebsocketClientMock(QiskitTestCase):
    """Tests for the the websocket client against a mock server."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Launch the mock server.
        start_server = websockets.serve(websocket_handler, '127.0.0.1', 8765)
        cls.server = asyncio.get_event_loop().run_until_complete(start_server)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        # Close the mock server.
        loop = asyncio.get_event_loop()
        loop.stop()
        # Manually cancel any pending asyncio tasks.
        pending = asyncio.Task.all_tasks()
        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                loop.run_until_complete(task)

    def test_job_final_status(self):
        client = WebsocketClient('ws://127.0.0.1:8765', TOKEN_JOB_COMPLETED)
        response = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_job_transition(self):
        client = WebsocketClient('ws://127.0.0.1:8765', TOKEN_JOB_TRANSITION)
        response = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))
        self.assertIsInstance(response, dict)
        self.assertIn('status', response)
        self.assertEqual(response['status'], 'COMPLETED')

    def test_timeout(self):
        client = WebsocketClient('ws://127.0.0.1:8765', TOKEN_TIMEOUT)
        with self.assertRaises(WebsocketTimeoutError):
            _ = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id', timeout=2))

    def test_invalid_response(self):
        client = WebsocketClient('ws://127.0.0.1:8765', TOKEN_WRONG_FORMAT)
        with self.assertRaises(WebsocketIBMQProtocolError):
            _ = asyncio.get_event_loop().run_until_complete(
                client.get_job_status('job_id'))
