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

import time

from qiskit.providers.ibmq.runtime import RuntimeJob
from qiskit.providers.ibmq.runtime.exceptions import RuntimeInvalidStateError
from qiskit.providers.ibmq.credentials import Credentials
from qiskit.test.mock.fake_qasm_simulator import FakeQasmSimulator

from ...ibmqtestcase import IBMQTestCase
from ...ws_server import MockWsServer
from .ws_handler import (websocket_handler, JOB_ID_PROGRESS_DONE, JOB_ID_ALREADY_DONE,
                         JOB_ID_RETRY_SUCCESS, JOB_ID_RETRY_FAILURE,
                         JOB_PROGRESS_RESULT_COUNT)
from .fake_runtime_client import BaseFakeRuntimeClient


class TestRuntimeWebsocketClient(IBMQTestCase):
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

        # Close the mock server.
        cls.server.stop()

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
        self.assertFalse(job._ws_client.connected)

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
        self.assertFalse(job._ws_client.connected)

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
        for _ in range(10):
            self.log.debug("Waiting for client to finish disconnect.")
            if not job._ws_client.connected:
                break
            time.sleep(1)
        self.assertFalse(job._ws_client.connected)

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
        self.assertFalse(job._ws_client.connected)

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
        self.assertFalse(job._ws_client.connected)

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
        self.assertFalse(job._ws_client.connected)

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
        self.assertFalse(job._ws_client.connected)

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
        self.assertFalse(job._ws_client.connected)

    def _get_job(self, callback=None, job_id=JOB_ID_PROGRESS_DONE):
        """Get a runtime job."""
        cred = Credentials(token="my_token", url="",
                           services={"runtime": MockWsServer.VALID_WS_URL})
        job = RuntimeJob(backend=FakeQasmSimulator(),
                         api_client=BaseFakeRuntimeClient(),
                         credentials=cred,
                         job_id=job_id,
                         program_id="my-program",
                         user_callback=callback)
        return job
