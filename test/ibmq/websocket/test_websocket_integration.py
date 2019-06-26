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
from qiskit.providers.ibmq import IBMQ, least_busy
from qiskit.providers.ibmq.api_v2.websocket import WebsocketClient, WebsocketMessage
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob
from qiskit.providers.jobstatus import JobStatus
from qiskit.test import QiskitTestCase, slow_test

from ...decorators import requires_new_api_auth, requires_qe_access


class TestWebsocketIntegration(QiskitTestCase):
    """Websocket integration tests."""

    # pylint: disable=arguments-differ
    @requires_qe_access
    @requires_new_api_auth
    def setUp(self, qe_token, qe_url):
        IBMQ.enable_account(qe_token, qe_url)
        self.sim_backend = IBMQ.get_backend('ibmq_qasm_simulator')
        # Create a circuit
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        self.qc1 = QuantumCircuit(qr, cr, name='qc1')
        self.qc1.measure(qr[0], cr[0])

        # Create and run a default Qobj using the simulator.
        self.circuit = transpile(self.qc1, backend=self.sim_backend)
        self.qobj = assemble(self.circuit, backend=self.sim_backend, shots=1)
        self.job = self.sim_backend.run(self.qobj)

    def test_websockets_simulator(self):
        """Test checking status of a job via websockets for a simulator."""
        # Manually disable the non-websocket polling.
        self.job._wait_for_final_status = None
        result = self.job.result()

        self.assertEqual(result.status, 'COMPLETED')

    @slow_test
    def test_websockets_device(self):
        """Test checking status of a job via websockets for a device."""
        backend = least_busy(IBMQ.backends(simulator=False))

        qc = transpile(self.qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        # Manually disable the non-websocket polling.
        job._wait_for_final_status = None
        result = job.result()

        self.assertEqual(result.status, 'COMPLETED')

    def test_websockets_job_final_state(self):
        """Test checking status of a job in a final state via websockets."""
        # Cancel the job to put it in a final (cancelled) state.
        self.job.cancel()
        self.job._wait_for_completion()
        self.assertIs(self.job._status, JobStatus.CANCELLED)

    def test_websockets_retry_bad_url(self):
        """Test http retry after websocket error due to an invalid URL."""
        # Use fake websocket address.
        self.job._api.client_ws.websocket_url = 'wss://wss.wayne-enterprises.com'

        # _wait_for_completion() should retry with http successfully after getting websockets error.
        self.job._wait_for_completion()
        self.assertIs(self.job._status, JobStatus.DONE)

    @mock.patch.object(WebsocketClient, '_authentication_message',
                       return_value=WebsocketMessage(type_='authentication', data='phantom_token'))
    def test_websockets_retry_bad_auth(self, _):
        """Test http retry after websocket error due to a failed authentication."""
        with mock.patch.object(IBMQJob, '_wait_for_final_status',
                               side_effect=self.job._wait_for_final_status) as mocked_wait:
            self.job._wait_for_completion()
            self.assertIs(self.job._status, JobStatus.DONE)
            mocked_wait.assert_called_with(mock.ANY, mock.ANY)

    def test_websockets_retry_connection_closed(self):
        """Test http retry after websocket error due to closed connection."""

        def _final_status_side_effect(*args, **kwargs):
            """Side effect function to restore job ID"""
            self.job._job_id = saved_job_id
            return saved_wait_for_final_status(*args, **kwargs)

        self.job._wait_for_submission()

        # Save the originals.
        saved_job_id = self.job._job_id
        saved_wait_for_final_status = self.job._wait_for_final_status
        # Use bad job ID to fail the status retrieval.
        self.job._job_id = '12345'

        # job.result() should retry with http successfully after getting websockets error.
        with mock.patch.object(IBMQJob, '_wait_for_final_status',
                               side_effect=_final_status_side_effect):
            self.job._wait_for_completion()
            self.assertIs(self.job._status, JobStatus.DONE)

    @slow_test
    def test_websockets_timeout(self):
        """Test timeout checking status of a job via websockets."""
        backend = IBMQ.get_backend('ibmqx4')

        qc = transpile(self.qc1, backend=backend)
        qobj = assemble(qc, backend=backend)
        job = backend.run(qobj)

        job._wait_for_submission()
        with self.assertRaises(JobTimeoutError):
            job.result(timeout=0.1)

    def test_websockets_multi_job(self):
        """Test checking status of multiple jobs in parallel via websockets."""

        def _run_job_get_result(q):
            job = self.sim_backend.run(self.qobj)
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
