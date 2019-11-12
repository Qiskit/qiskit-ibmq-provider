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

"""Test for the Websocket client integration."""

from unittest import mock
from threading import Thread
from queue import Queue

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.providers import JobTimeoutError
from qiskit.providers.ibmq.api.clients.websocket import (
    WebsocketClient, WebsocketAuthenticationMessage)
from qiskit.providers.ibmq.api.clients import AccountClient
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
from qiskit.providers.jobstatus import JobStatus

from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_qe_access, run_on_device


class TestWebsocketIntegration(IBMQTestCase):
    """Websocket integration tests."""

    @classmethod
    @requires_qe_access
    def _get_provider(cls, qe_token=None, qe_url=None):
        """Helper for getting account credentials."""
        ibmq_factory = IBMQFactory()
        provider = ibmq_factory.enable_account(qe_token, qe_url)
        return provider

    def setUp(self):
        self.provider = self._get_provider()
        self.sim_backend = self.provider.get_backend(simulator=True)

        # Create a circuit
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        self.qc1 = QuantumCircuit(qr, cr, name='qc1')
        self.qc1.measure(qr[0], cr[0])

        # Create a default Qobj using the simulator.
        self.circuit = transpile(self.qc1, backend=self.sim_backend)
        self.qobj = assemble(self.circuit, backend=self.sim_backend, shots=1)

    def test_websockets_simulator(self):
        """Test checking status of a job via websockets for a simulator."""
        job = self.sim_backend.run(self.qobj)

        # Manually disable the non-websocket polling.
        job._api._job_final_status_polling = None
        result = job.result()

        self.assertEqual(result.status, 'COMPLETED')

    @run_on_device
    def test_websockets_device(self, provider, backend):  # pylint: disable=unused-argument
        """Test checking status of a job via websockets for a device."""
        qc = transpile(self.qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        # Manually disable the non-websocket polling.
        job._api._job_final_status_polling = None
        result = job.result(timeout=180)

        self.assertTrue(result.success)

    def test_websockets_job_final_state(self):
        """Test checking status of a job in a final state via websockets."""
        job = self.sim_backend.run(self.qobj)

        job._wait_for_completion()

        # Manually disable the non-websocket polling.
        job._api._job_final_status_polling = None

        # Pretend we haven't seen the final status
        job._status = JobStatus.RUNNING

        job._wait_for_completion()
        self.assertIs(job._status, JobStatus.DONE)

    def test_websockets_retry_bad_url(self):
        """Test http retry after websocket error due to an invalid URL."""
        job = self.sim_backend.run(self.qobj)

        saved_websocket_url = job._api.client_ws.websocket_url
        try:
            # Use fake websocket address.
            job._api.client_ws.websocket_url = 'wss://wss.localhost'

            # _wait_for_completion() should retry with http successfully
            # after getting websockets error.
            job._wait_for_completion()
        finally:
            job._api.client_ws.websocket_url = saved_websocket_url

        self.assertIs(job._status, JobStatus.DONE)

    @mock.patch.object(WebsocketClient, '_authentication_message',
                       return_value=WebsocketAuthenticationMessage(
                           type_='authentication', data='phantom_token'))
    def test_websockets_retry_bad_auth(self, _):
        """Test http retry after websocket error due to a failed authentication."""
        job = self.sim_backend.run(self.qobj)

        with mock.patch.object(AccountClient, 'job_status',
                               side_effect=job._api.job_status) as mocked_wait:
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

        job = self.sim_backend.run(self.qobj)

        # Save the originals.
        saved_job_id = job._job_id
        saved_job_status = job._api.job_status
        # Use bad job ID to fail the status retrieval.
        job._job_id = '12345'

        # job.result() should retry with http successfully after getting websockets error.
        with mock.patch.object(AccountClient, 'job_status',
                               side_effect=_job_status_side_effect):
            job._wait_for_completion()
            self.assertIs(job._status, JobStatus.DONE)

    def test_websockets_timeout(self):
        """Test timeout checking status of a job via websockets."""
        qc = transpile(self.qc1, backend=self.sim_backend)
        qobj = assemble(qc, backend=self.sim_backend, shots=2048)
        job = self.sim_backend.run(qobj)

        with self.assertRaises(JobTimeoutError):
            job.result(timeout=0.1)

    def test_websockets_multi_job(self):
        """Test checking status of multiple jobs in parallel via websockets."""

        def _run_job_get_result(q):
            job = self.sim_backend.run(self.qobj)
            # Manually disable the non-websocket polling.
            job._api._job_final_status_polling = None
            job._wait_for_completion()
            if job._status is not JobStatus.DONE:
                q.put(False)

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

        self.assertTrue(result_q.empty())
