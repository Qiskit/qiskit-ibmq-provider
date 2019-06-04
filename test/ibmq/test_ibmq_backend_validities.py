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

"""IBMQ Remote Backend Qobj Tests."""

import os

from qiskit import (BasicAer, ClassicalRegister, QuantumCircuit,
                    QuantumRegister)
from qiskit.providers.ibmq import IBMQ
from qiskit.test import QiskitTestCase, slow_test
from qiskit.compiler import transpile

from ..decorators import requires_qe_access


class TestIBMQBackendValidities(QiskitTestCase):
    """Qiskit backend qobj test.

    Executes a series of circuits of special interest using remote
    simulators as configured in environment variables
    'IBMQ_QOBJ_DEVICE', 'IBMQ_TOKEN' and 'IBMQ_QOBJ_URL', comparing
    results against local simulator 'local_qasm_simulator' as ground
    truth.
    """

    def setUp(self):
        super().setUp()
        self._testing_device = os.getenv('IBMQ_QOBJ_DEVICE', None)
        self._qe_token = os.getenv('IBMQ_TOKEN', None)
        self._qe_url = os.getenv('IBMQ_QOBJ_URL')

        if not self._testing_device or not self._qe_token or not self._qe_url:
            self.skipTest("No credentials or testing device available for "
                          "testing Qobj capabilities.")

        IBMQ.enable_account(self._qe_token, self._qe_url)
        self._local_backend = BasicAer.get_backend('qasm_simulator')
        self._remote_backend = IBMQ.get_backend(self._testing_device)
        self.log.info('Remote backend: %s', self._remote_backend.name())
        self.log.info('Local backend: %s', self._local_backend.name())

    @slow_test
    @requires_qe_access
    def test_one_qubit_no_operation(self):
        """Test one circuit, one register, in-order readout."""
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        circuit = QuantumCircuit(qr, cr)
        circuit.measure(qr[0], cr[0])

        qobj = transpile(circuit, backend=self._remote_backend)
        result_remote = self._remote_backend.run(qobj).result()
        result_local = self._local_backend.run(qobj).result()
        self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                   result_local.get_counts(circuit), delta=50)

    @slow_test
    @requires_qe_access
    def test_one_qubit_operation(self):
        """Test one circuit, one register, in-order readout."""
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.measure(qr[0], cr[0])

        qobj = transpile(circuit, backend=self._remote_backend)
        result_remote = self._remote_backend.run(qobj).result()
        result_local = self._local_backend.run(qobj).result()
        self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                   result_local.get_counts(circuit), delta=50)

    @slow_test
    @requires_qe_access
    def test_simple_circuit(self):
        """Test one circuit, one register, in-order readout."""
        qr = QuantumRegister(4)
        cr = ClassicalRegister(4)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.x(qr[2])
        circuit.measure(qr[0], cr[0])
        circuit.measure(qr[1], cr[1])
        circuit.measure(qr[2], cr[2])
        circuit.measure(qr[3], cr[3])

        qobj = transpile(circuit, backend=self._remote_backend)
        result_remote = self._remote_backend.run(qobj).result()
        result_local = self._local_backend.run(qobj).result()
        self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                   result_local.get_counts(circuit), delta=50)

    @slow_test
    @requires_qe_access
    def test_readout_order(self):
        """Test one circuit, one register, out-of-order readout.
        """
        qr = QuantumRegister(4)
        cr = ClassicalRegister(4)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.x(qr[2])
        circuit.measure(qr[0], cr[2])
        circuit.measure(qr[1], cr[0])
        circuit.measure(qr[2], cr[1])
        circuit.measure(qr[3], cr[3])

        qobj_remote = transpile(circuit, backend=self._remote_backend)
        qobj_local = transpile(circuit, backend=self._local_backend)
        result_remote = self._remote_backend.run(qobj_remote).result()
        result_local = self._local_backend.run(qobj_local).result()
        self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                   result_local.get_counts(circuit), delta=50)

    @slow_test
    @requires_qe_access
    def test_multi_register(self):
        """Test one circuit, two registers, out-of-order readout."""
        qr1 = QuantumRegister(2)
        qr2 = QuantumRegister(2)
        cr1 = ClassicalRegister(3)
        cr2 = ClassicalRegister(1)
        circuit = QuantumCircuit(qr1, qr2, cr1, cr2)
        circuit.h(qr1[0])
        circuit.cx(qr1[0], qr2[1])
        circuit.h(qr2[0])
        circuit.cx(qr2[0], qr1[1])
        circuit.x(qr1[1])
        circuit.measure(qr1[0], cr2[0])
        circuit.measure(qr1[1], cr1[0])
        circuit.measure(qr1[1], cr2[0])
        circuit.measure(qr1[1], cr1[2])
        circuit.measure(qr2[0], cr1[2])
        circuit.measure(qr2[1], cr1[1])

        qobj = transpile(circuit, backend=self._remote_backend)
        result_remote = self._remote_backend.run(qobj).result()
        result_local = self._local_backend.run(qobj).result()
        self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                   result_local.get_counts(circuit), delta=50)

    @slow_test
    @requires_qe_access
    def test_multi_circuit(self):
        """Test two circuits, two registers, out-of-order readout."""
        qr1 = QuantumRegister(2)
        qr2 = QuantumRegister(2)
        cr1 = ClassicalRegister(3)
        cr2 = ClassicalRegister(1)
        circuit1 = QuantumCircuit(qr1, qr2, cr1, cr2)
        circuit1.h(qr1[0])
        circuit1.cx(qr1[0], qr2[1])
        circuit1.h(qr2[0])
        circuit1.cx(qr2[0], qr1[1])
        circuit1.x(qr1[1])
        circuit1.measure(qr1[0], cr2[0])
        circuit1.measure(qr1[1], cr1[0])
        circuit1.measure(qr1[0], cr2[0])
        circuit1.measure(qr1[1], cr1[2])
        circuit1.measure(qr2[0], cr1[2])
        circuit1.measure(qr2[1], cr1[1])
        circuit2 = QuantumCircuit(qr1, qr2, cr1)
        circuit2.h(qr1[0])
        circuit2.cx(qr1[0], qr1[1])
        circuit2.h(qr2[1])
        circuit2.cx(qr2[1], qr1[1])
        circuit2.measure(qr1[0], cr1[0])
        circuit2.measure(qr1[1], cr1[1])
        circuit2.measure(qr1[0], cr1[2])
        circuit2.measure(qr2[1], cr1[2])

        qobj = transpile([circuit1, circuit2], backend=self._remote_backend)
        result_remote = self._remote_backend.run(qobj).result()
        result_local = self._local_backend.run(qobj).result()
        self.assertDictAlmostEqual(result_remote.get_counts(circuit1),
                                   result_local.get_counts(circuit1), delta=50)
        self.assertDictAlmostEqual(result_remote.get_counts(circuit2),
                                   result_local.get_counts(circuit2), delta=50)
