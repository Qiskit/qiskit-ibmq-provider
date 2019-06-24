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
from qiskit.providers.ibmq import least_busy
from qiskit.test import QiskitTestCase, slow_test

from ...decorators import requires_provider


class TestWebsocketIntegration(QiskitTestCase):
    """Websocket integration tests."""

    def setUp(self):
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        self._qc1 = QuantumCircuit(qr, cr, name='qc1')
        self._qc1.measure(qr[0], cr[0])

    @requires_provider
    def test_websockets_simulator(self, provider):
        """Test checking status of a job via websockets for a simulator."""
        backend = provider.get_backend(simulator=True)

        qc = transpile(self._qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        # Manually disable the non-websocket pooling.
        job._wait_for_final_status = None
        result = job.result()

        self.assertEqual(result.status, 'COMPLETED')

    @slow_test
    @requires_provider
    def test_websockets_device(self, provider):
        """Test checking status of a job via websockets for a device."""
        backend = least_busy(provider.backends(simulator=False))

        qc = transpile(self._qc1, backend=backend)
        qobj = assemble(qc, backend=backend)

        job = backend.run(qobj)
        # Manually disable the non-websocket pooling.
        job._wait_for_final_status = None
        result = job.result()

        self.assertEqual(result.status, 'COMPLETED')
