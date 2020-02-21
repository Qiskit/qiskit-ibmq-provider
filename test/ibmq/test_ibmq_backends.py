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

"""Test remote backends."""

from unittest import skip

from qiskit import (BasicAer, ClassicalRegister, QuantumCircuit,
                    QuantumRegister)
from qiskit.test import slow_test
from qiskit.compiler import assemble, transpile

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


@skip('Skipping since they should be run by backend.')
class TestIBMQBackends(IBMQTestCase):
    """Tests for remote backend validation.

    Execute a series of circuits of special interest using
    all available remote backends, comparing results against
    local simulator 'local_qasm_simulator' as ground truth.
    """

    @slow_test
    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self._local_backend = BasicAer.get_backend('qasm_simulator')
        self._remote_backends = self.get_backends()

    @requires_provider
    def get_backends(self, provider=None):
        """Return all available remote backends."""
        return provider.backends()

    def test_one_qubit_no_operation(self):
        """Test one circuit, one register, in-order readout."""
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        circuit = QuantumCircuit(qr, cr)
        circuit.measure(qr[0], cr[0])

        qobj = assemble(transpile(circuit, backend=self._local_backend))
        result_local = self._local_backend.run(qobj, validate_qobj=True).result()

        for remote_backend in self._remote_backends:
            if not remote_backend.status().operational:
                continue
            with self.subTest(backend=remote_backend):
                result_remote = remote_backend.run(qobj, validate_qobj=True).result()
                self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                           result_local.get_counts(circuit), delta=50)

    def test_one_qubit_operation(self):
        """Test one circuit, one register, in-order readout."""
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.measure(qr[0], cr[0])

        qobj = assemble(transpile(circuit, backend=self._local_backend))
        result_local = self._local_backend.run(qobj, validate_qobj=True).result()

        for remote_backend in self._remote_backends:
            with self.subTest(backend=remote_backend):
                result_remote = remote_backend.run(qobj, validate_qobj=True).result()
                self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                           result_local.get_counts(circuit), delta=50)

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

        qobj = assemble(transpile(circuit, backend=self._local_backend))
        result_local = self._local_backend.run(qobj, validate_qobj=True).result()

        for remote_backend in self._remote_backends:
            with self.subTest(backend=remote_backend):
                result_remote = remote_backend.run(qobj, validate_qobj=True).result()
                self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                           result_local.get_counts(circuit), delta=50)

    def test_readout_order(self):
        """Test one circuit, one register, out-of-order readout."""
        qr = QuantumRegister(4)
        cr = ClassicalRegister(4)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.x(qr[2])
        circuit.measure(qr[0], cr[2])
        circuit.measure(qr[1], cr[0])
        circuit.measure(qr[2], cr[1])
        circuit.measure(qr[3], cr[3])

        qobj_local = assemble(transpile(circuit, backend=self._local_backend))
        result_local = self._local_backend.run(qobj_local, validate_qobj=True).result()

        for remote_backend in self._remote_backends:
            with self.subTest(backend=remote_backend):
                qobj_remote = assemble(transpile(circuit, backend=remote_backend))
                result_remote = remote_backend.run(qobj_remote, validate_qobj=True).result()
                self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                           result_local.get_counts(circuit), delta=50)

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

        qobj = assemble(transpile(circuit, backend=self._local_backend))
        result_local = self._local_backend.run(qobj, validate_qobj=True).result()

        for remote_backend in self._remote_backends:
            with self.subTest(backend=remote_backend):
                result_remote = remote_backend.run(qobj, validate_qobj=True).result()
                self.assertDictAlmostEqual(result_remote.get_counts(circuit),
                                           result_local.get_counts(circuit), delta=50)

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

        qobj = assemble(transpile([circuit1, circuit2], backend=self._local_backend))
        result_local = self._local_backend.run(qobj, validate_qobj=True).result()

        for remote_backend in self._remote_backends:
            with self.subTest(backend=remote_backend):
                result_remote = remote_backend.run(qobj, validate_qobj=True).result()
                self.assertDictAlmostEqual(result_remote.get_counts(circuit1),
                                           result_local.get_counts(circuit1), delta=50)
                self.assertDictAlmostEqual(result_remote.get_counts(circuit2),
                                           result_local.get_counts(circuit2), delta=50)
