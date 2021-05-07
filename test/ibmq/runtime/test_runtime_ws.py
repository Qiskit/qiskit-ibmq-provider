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
import asyncio
import warnings
from contextlib import suppress
import time
from concurrent.futures import ThreadPoolExecutor
import threading

import websockets

from qiskit.providers.ibmq.api.clients.runtime_ws import RuntimeWebsocketClient
from qiskit.providers.ibmq.runtime import RuntimeJob
from qiskit.providers.ibmq.runtime.exceptions import RuntimeInvalidStateError
from qiskit.test.mock.fake_qasm_simulator import FakeQasmSimulator

from ...ibmqtestcase import IBMQTestCase
from .websocket_server import (websocket_handler, JOB_ID_PROGRESS_DONE, JOB_ID_ALREADY_DONE,
                               JOB_ID_RETRY_SUCCESS, JOB_ID_RETRY_FAILURE,
                               JOB_PROGRESS_RESULT_COUNT)
from .fake_runtime_client import BaseFakeRuntimeClient


class TestRuntimeWebsocketClient(IBMQTestCase):
    """Tests for the the websocket client against a mock server."""

    TEST_IP_ADDRESS = '127.0.0.1'
    INVALID_PORT = 9876
    VALID_PORT = 8765
    VALID_URL = f"ws://{TEST_IP_ADDRESS}:{VALID_PORT}"

    _executor = ThreadPoolExecutor()

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        super().setUpClass()

        # Launch the mock server.
        cls._ws_stop_event = threading.Event()
        cls._ws_start_event = threading.Event()
        cls._future = cls._executor.submit(cls._ws_server)
        cls._ws_start_event.wait(5)

    @classmethod
    def _ws_server(cls):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Launch the mock server.
        # pylint: disable=no-member
        start_server = websockets.serve(websocket_handler, cls.TEST_IP_ADDRESS, cls.VALID_PORT)
        cls.server = loop.run_until_complete(start_server)
        cls._ws_start_event.set()

        # A bit hacky but we need to keep the loop running to serve the request.
        # An there's no easy way to interrupt a run_forever.
        while not cls._ws_stop_event.is_set():
            loop.run_until_complete(asyncio.sleep(1))

        cls.server.close()
        loop.run_until_complete(cls.server.wait_closed())

        with warnings.catch_warnings():
            # Suppress websockets deprecation warning
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            # Manually cancel any pending asyncio tasks.
            if sys.version_info[0:2] < (3, 9):
                pending = asyncio.Task.all_tasks()
            else:
                pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    loop.run_until_complete(task)
            except Exception as err:  # pylint: disable=broad-except
                cls.log.error("An error %s occurred canceling task %s. "
                              "Traceback:", str(err), str(task))
                task.print_stack()

    @classmethod
    def tearDownClass(cls):
        """Class level cleanup."""
        super().tearDownClass()

        # Close the mock server.
        cls._ws_stop_event.set()
        cls._future.result()

    def test_interim_result_callback(self):
        """Test interim result callback."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_PROGRESS_DONE, job_id)

        results = []
        job = self._get_job(callback=result_callback)
        time.sleep(JOB_PROGRESS_RESULT_COUNT+2)
        self.assertEqual(JOB_PROGRESS_RESULT_COUNT, len(results))
        self.assertIsNone(job._ws_client._ws)

    def test_stream_results(self):
        """Test streaming results."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_PROGRESS_DONE, job_id)

        results = []
        job = self._get_job()
        job.stream_results(callback=result_callback)
        time.sleep(JOB_PROGRESS_RESULT_COUNT+2)
        self.assertEqual(JOB_PROGRESS_RESULT_COUNT, len(results))
        self.assertIsNone(job._ws_client._ws)

    def test_duplicate_streaming(self):
        """Testing duplicate streaming."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_PROGRESS_DONE, job_id)

        results = []
        job = self._get_job(callback=result_callback)
        time.sleep(1)
        with self.assertRaises(RuntimeInvalidStateError):
            job.stream_results(callback=result_callback)

    def test_cancel_streaming(self):
        """Test canceling streaming."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_PROGRESS_DONE, job_id)

        results = []
        job = self._get_job(callback=result_callback)
        time.sleep(1)
        job.cancel_result_streaming()
        time.sleep(1)
        self.assertIsNone(job._ws_client._ws)

    def test_cancel_closed_streaming(self):
        """Test canceling streaming that's already closed."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_ALREADY_DONE, job_id)

        results = []
        job = self._get_job(callback=result_callback, job_id=JOB_ID_ALREADY_DONE)
        time.sleep(2)
        job.cancel_result_streaming()
        self.assertIsNone(job._ws_client._ws)

    def test_completed_job(self):
        """Test callback from completed job."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_ALREADY_DONE, job_id)

        results = []
        job = self._get_job(callback=result_callback, job_id=JOB_ID_ALREADY_DONE)
        time.sleep(2)
        self.assertEqual(0, len(results))
        self.assertIsNone(job._ws_client._ws)

    def test_completed_job_stream(self):
        """Test streaming from completed job."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_ALREADY_DONE, job_id)

        results = []
        job = self._get_job(job_id=JOB_ID_ALREADY_DONE)
        job.stream_results(callback=result_callback)
        time.sleep(2)
        self.assertEqual(0, len(results))
        self.assertIsNone(job._ws_client._ws)

    def test_websocket_retry_success(self):
        """Test successful retry."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_RETRY_SUCCESS, job_id)

        results = []
        job = self._get_job(job_id=JOB_ID_RETRY_SUCCESS, callback=result_callback)
        time.sleep(JOB_PROGRESS_RESULT_COUNT+2)
        self.assertEqual(JOB_PROGRESS_RESULT_COUNT, len(results))
        self.assertIsNone(job._ws_client._ws)

    def test_websocket_retry_failure(self):
        """Test failed retry."""
        def result_callback(job_id, interim_result):
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_RETRY_FAILURE, job_id)

        results = []
        job = self._get_job(job_id=JOB_ID_RETRY_FAILURE, callback=result_callback)
        time.sleep(20)  # Need to wait for all retries.
        self.assertEqual(0, len(results))
        self.assertIsNone(job._ws_client._ws)

    def _get_job(self, callback=None, job_id=JOB_ID_PROGRESS_DONE):
        """Get a runtime job."""
        ws_client = RuntimeWebsocketClient(self.VALID_URL, "my_token")
        job = RuntimeJob(backend=FakeQasmSimulator(),
                         api_client=BaseFakeRuntimeClient(),
                         ws_client=ws_client,
                         job_id=job_id,
                         program_id="my-program",
                         user_callback=callback)
        return job
