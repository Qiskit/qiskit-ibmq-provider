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

"""Test for the Websocket client integration."""

import logging
import os
import time
from queue import Queue
from threading import Thread
from typing import List, Union
from unittest import mock
from unittest.case import skipIf

from qiskit import transpile
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.providers import Backend, JobTimeoutError
from qiskit.providers.ibmq.api.clients import AccountClient, websocket
from qiskit.providers.ibmq.exceptions import IBMQBackendJobLimitError
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.job import JobV1 as Job
from qiskit.providers.jobstatus import JobStatus
from qiskit.test import slow_test
from qiskit.test.reference_circuits import ReferenceCircuits

from ...decorators import requires_device, requires_provider
from ...ibmqtestcase import IBMQTestCase
from ...proxy_server import MockProxyServer, use_proxies
from ...utils import cancel_job, most_busy_backend

logger = logging.getLogger(__name__)


class TestWebsocketIntegration(IBMQTestCase):
    """Websocket integration tests."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.sim_backend: IBMQBackend = provider.get_backend('ibmq_qasm_simulator')
        cls.bell = transpile(ReferenceCircuits.bell(), cls.sim_backend)
        # Setup list of jobs to check have been deleted.
        cls.jobs_to_delete: List[str] = []

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.saved_status_polling = self.sim_backend._api_client._job_final_status_polling

    def tearDown(self):
        """Test tear down."""
        super().tearDown()
        self.sim_backend._api_client._job_final_status_polling = self.saved_status_polling

    def _job_final_status_polling(self, *args, **kwargs):
        """Replaces the actual _job_final_status_polling and fails the test."""
        # pylint: disable=unused-argument
        self.fail("Obtaining job status via websockets failed!")

    def test_websockets_simulator(self):
        """Test checking status of a job via websockets for a simulator."""
        job = self._sim_job(shots=1)

        # Manually disable the non-websocket polling.
        job._api_client._job_final_status_polling = self._job_final_status_polling
        result = job.result()
        job.wait_for_final_state()

        self.assertEqual(result.status, 'COMPLETED')

    @slow_test
    @requires_device
    def test_websockets_device(self, backend):
        """Test checking status of a job via websockets for a device."""
        job = self._sim_job(backend=backend, shots=1)

        # Manually disable the non-websocket polling.
        job._api_client._job_final_status_polling = self._job_final_status_polling
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result = job.result()
        job.wait_for_final_state()

        self.assertTrue(result.success)

    def test_websockets_job_final_state(self):
        """Test checking status of a job in a final state via websockets."""
        job = self._sim_job()

        job._wait_for_completion()

        # Manually disable the non-websocket polling.
        job._api_client._job_final_status_polling = self._job_final_status_polling

        # Pretend we haven't seen the final status
        job._status = JobStatus.RUNNING

        job._wait_for_completion()
        self.assertIs(job._status, JobStatus.DONE)

    def test_websockets_retry_bad_url(self):
        """Test http retry after websocket error due to an invalid URL."""

        job = self._sim_job()

        saved_websocket_url = job._api_client._credentials.websockets_url

        try:
            # Use fake websocket address.
            job._api_client._credentials.websockets_url = 'wss://wss.localhost'

            # _wait_for_completion() should retry with http successfully
            # after getting websockets error.
            job._wait_for_completion()
        finally:
            job._api_client._credentials.websockets_url = saved_websocket_url

        self.assertIs(job._status, JobStatus.DONE)

    def test_websockets_retry_bad_auth(self):
        """Test http retry after websocket error due to a failed authentication."""
        job = self._sim_job()
        with mock.patch.object(websocket.WebsocketAuthenticationMessage, 'as_json',
                               return_value='foo'), \
            mock.patch.object(AccountClient, 'job_status',
                              side_effect=job._api_client.job_status) as mocked_wait:
            job._wait_for_completion()
            self.assertIs(job._status, JobStatus.DONE)
            mocked_wait.assert_called_with(job.job_id())

    def test_websockets_retry_connection_closed(self):
        """Test http retry after websocket error due to closed connection."""

        def _job_status_side_effect(*args, **kwargs):
            """Side effect function to restore job ID"""
            # pylint: disable=unused-argument
            job._job_id = saved_job_id
            return saved_job_status(saved_job_id)

        job = self._sim_job()
        # Save the originals.
        saved_job_id = job._job_id
        saved_job_status = job._api_client.job_status
        # Use bad job ID to fail the status retrieval.
        job._job_id = '12345'

        # job.result() should retry with http successfully after getting websockets error.
        with mock.patch.object(AccountClient, 'job_status',
                               side_effect=_job_status_side_effect):
            job._wait_for_completion()
            self.assertIs(
                job._status, JobStatus.DONE,
                "Job {} status is {} when it should be DONE.".format(job.job_id(), job._status))

    def test_websockets_timeout(self):
        """Test timeout checking status of a job via websockets."""
        backend = most_busy_backend(self.provider)
        job = self._sim_job(shots=backend.configuration().max_shots)

        try:
            with self.assertRaises(JobTimeoutError):
                job.result(timeout=0.1)
        finally:
            cancel_job(job)

    @skipIf(os.environ.get('LIMIT_CONCURRENT_JOBS', ''), 'Protects concurrent job limit')
    def test_websockets_multi_job(self):
        """Test checking status of multiple jobs in parallel via websockets."""

        def _run_job_get_result(q):
            """Run a job and get its result."""
            job = self._sim_job()
            # Manually disable the non-websocket polling.
            job._api_client._job_final_status_polling = self._job_final_status_polling
            job._wait_for_completion()
            if job._status is not JobStatus.DONE:
                q.put("Job {} status should be DONE but is {}".format(
                    job.job_id(), job._status.name))

        max_threads = 2
        result_q = Queue()
        job_threads = []

        for i in range(max_threads):
            job_thread = Thread(target=_run_job_get_result, args=(result_q,),
                                name="job_result_{}".format(i), daemon=True)
            job_thread.start()
            job_threads.append(job_thread)

        for job_thread in job_threads:
            job_thread.join()

        if not result_q.empty():
            message = result_q.get_nowait()
            self.fail(message)

    def test_websocket_proxy(self):
        """Test connecting to websocket via a proxy."""
        MockProxyServer(self, self.log).start()
        job = self._sim_job(shots=1)

        # Manually disable the non-websocket polling.
        job._api_client._job_final_status_polling = self._job_final_status_polling
        with use_proxies(self.provider, MockProxyServer.VALID_PROXIES):
            result = job.result()

        self.assertEqual(result.status, 'COMPLETED')

    def test_websocket_proxy_invalid_port(self):
        """Test connecting to websocket via invalid proxy port."""
        MockProxyServer(self, self.log).start()
        job = self.sim_backend.run(self.bell, shots=1)

        invalid_proxy = {'https': 'http://{}:{}'.format(MockProxyServer.PROXY_IP_ADDRESS,
                                                        MockProxyServer.INVALID_PROXY_PORT)}
        with use_proxies(self.provider, invalid_proxy):
            with self.assertLogs('qiskit.providers.ibmq', 'INFO') as log_cm:
                job.wait_for_final_state()

        self.assertIn("retrying using HTTP", ','.join(log_cm.output))

    def _sim_job(self, backend: Backend = None, max_retries: int = 10,
                 qc: Union[QuantumCircuit, List[QuantumCircuit]] = None, **kwargs) -> Job:
        # Default to the bell circuit
        qc = qc or self.bell
        backend = backend or self.sim_backend
        # Simulate circuit
        while max_retries >= 0:
            try:
                return backend.run(self.bell, **kwargs)
            except IBMQBackendJobLimitError:
                logger.info('Cannot submit job, trying again.. %d attempts remaining.', max_retries)
            time.sleep(5)
            max_retries -= 1
        return None
