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

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.providers.ibmq import IBMQ, least_busy
from qiskit.providers.ibmq.api_v2.exceptions import (
    WebsocketError, WebsocketTimeoutError, WebsocketIBMQProtocolError)
from qiskit.test import QiskitTestCase, slow_test

from ...decorators import requires_new_api_auth, requires_qe_access


class TestWebsocketIntegration(QiskitTestCase):
    """Websocket integration tests."""

    @classmethod
    @requires_qe_access
    @requires_new_api_auth
    def setUpClass(cls, qe_token, qe_url):
        super().setUpClass()

        IBMQ.enable_account(qe_token, qe_url)

        # Create a circuit
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        cls._qc1 = QuantumCircuit(qr, cr, name='qc1')
        cls._qc1.measure(qr[0], cr[0])

    def test_websockets_simulator(self,):
        """Test checking status of a job via websockets for a simulator."""
        #IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend(simulator=True)

        qc = transpile(self._qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        # Manually disable the non-websocket polling.
        job._wait_for_final_status = None
        result = job.result()

        self.assertEqual(result.status, 'COMPLETED')

    @slow_test
    @requires_qe_access
    @requires_new_api_auth
    def test_websockets_device(self, qe_token, qe_url):
        """Test checking status of a job via websockets for a device."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = least_busy(IBMQ.backends(simulator=False))

        qc = transpile(self._qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        # Manually disable the non-websocket polling.
        job._wait_for_final_status = None
        result = job.result()

        self.assertEqual(result.status, 'COMPLETED')

    @requires_qe_access
    @requires_new_api_auth
    def test_websockets_job_final_state(self, qe_token, qe_url):
        """Test checking status of a job in a final state via websockets."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend(simulator=True)
        job = self._send_job_to_backend(backend)

        # Cancel the job to put it in a final state.
        job.cancel()
        job.result(timeout=1)

    @requires_qe_access
    @requires_new_api_auth
    def test_websockets_retry_bad_url(self, qe_token, qe_url):
        """Test checking status of a job via websockets for a simulator."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend(simulator=True)
        job = self._send_job_to_backend(backend)

        # Use fake websocket address.
        job._api.client_ws.websocket_url = 'wss://wss.wayne-enterprises.com'

        result = job.result()
        self.assertEqual(result.status, 'COMPLETED')

    @requires_qe_access
    @requires_new_api_auth
    def test_websockets_retry_bad_auth(self, qe_token, qe_url):
        """Test checking status of a job via websockets for a simulator."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend(simulator=True)
        job = self._send_job_to_backend(backend)

        # Use fake websocket address.
        job._api.client_ws.websocket_url = 'wss://wss.wayne-enterprises.com'

        result = job.result()
        self.assertEqual(result.status, 'COMPLETED')

    def _send_job_to_backend(self, backend):
        """Send a job a simulator.

        Args:
            backend (IBMQBackend): backend to send the job to.

        Returns:
            IBMQJob: an instance derived from BaseJob, representing the job.
        """
        qc = transpile(self._qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        return job

    # TODO test getting status after already got final status  (i.e. cancelled)
    # TODO test web socket error
    #   connection, authentication, etc?
    # TODO test timeout error?

    # TODO stress test
    # - checking status of multiple jobs
    # - multiple checking of same job
