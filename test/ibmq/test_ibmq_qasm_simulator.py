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

"""Test IBM Quantum online QASM simulator."""

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


class TestIbmqQasmSimulator(IBMQTestCase):
    """Test IBM Quantum QASM Simulator."""

    @requires_provider
    def test_execute_one_circuit_simulator_online(self, provider):
        """Test execute_one_circuit_simulator_online."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        qc = QuantumCircuit(qr, cr, name='qc')
        qc.h(qr[0])
        qc.measure(qr[0], cr[0])
        qobj = assemble(transpile(qc, backend=backend, seed_transpiler=73846087),
                        backend=backend)
        shots = qobj.config.shots
        job = backend.run(qobj, validate_qobj=True)
        result = job.result()
        counts = result.get_counts(qc)
        target = {'0': shots / 2, '1': shots / 2}
        threshold = 0.1 * shots
        self.assertDictAlmostEqual(counts, target, threshold)

    @requires_provider
    def test_execute_several_circuits_simulator_online(self, provider):
        """Test execute_several_circuits_simulator_online."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qr = QuantumRegister(2)
        cr = ClassicalRegister(2)
        qcr1 = QuantumCircuit(qr, cr, name='qc1')
        qcr2 = QuantumCircuit(qr, cr, name='qc2')
        qcr1.h(qr)
        qcr2.h(qr[0])
        qcr2.cx(qr[0], qr[1])
        qcr1.measure(qr[0], cr[0])
        qcr1.measure(qr[1], cr[1])
        qcr2.measure(qr[0], cr[0])
        qcr2.measure(qr[1], cr[1])
        shots = 1024
        qobj = assemble(transpile([qcr1, qcr2], backend=backend, seed_transpiler=73846087),
                        backend=backend, shots=shots)
        job = backend.run(qobj, validate_qobj=True)
        result = job.result()
        counts1 = result.get_counts(qcr1)
        counts2 = result.get_counts(qcr2)
        target1 = {'00': shots / 4, '01': shots / 4,
                   '10': shots / 4, '11': shots / 4}
        target2 = {'00': shots / 2, '11': shots / 2}
        threshold = 0.1 * shots
        self.assertDictAlmostEqual(counts1, target1, threshold)
        self.assertDictAlmostEqual(counts2, target2, threshold)

    @requires_provider
    def test_online_qasm_simulator_two_registers(self, provider):
        """Test online_qasm_simulator_two_registers."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qr1 = QuantumRegister(2)
        cr1 = ClassicalRegister(2)
        qr2 = QuantumRegister(2)
        cr2 = ClassicalRegister(2)
        qcr1 = QuantumCircuit(qr1, qr2, cr1, cr2, name="circuit1")
        qcr2 = QuantumCircuit(qr1, qr2, cr1, cr2, name="circuit2")
        qcr1.x(qr1[0])
        qcr2.x(qr2[1])
        qcr1.measure(qr1[0], cr1[0])
        qcr1.measure(qr1[1], cr1[1])
        qcr1.measure(qr2[0], cr2[0])
        qcr1.measure(qr2[1], cr2[1])
        qcr2.measure(qr1[0], cr1[0])
        qcr2.measure(qr1[1], cr1[1])
        qcr2.measure(qr2[0], cr2[0])
        qcr2.measure(qr2[1], cr2[1])
        qobj = assemble(transpile([qcr1, qcr2], backend, seed_transpiler=8458),
                        backend=backend, shots=1024)
        job = backend.run(qobj, validate_qobj=True)
        result = job.result()
        result1 = result.get_counts(qcr1)
        result2 = result.get_counts(qcr2)
        self.assertEqual(result1, {'00 01': 1024})
        self.assertEqual(result2, {'10 00': 1024})

    @requires_provider
    def test_conditional_operation(self, provider):
        """Test conditional operation."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qr = QuantumRegister(4)
        cr = ClassicalRegister(4)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.x(qr[2])
        circuit.measure(qr[0], cr[0])
        circuit.x(qr[0]).c_if(cr, 1)

        qobj = assemble(transpile(circuit, backend=backend))
        result = backend.run(qobj, validate_qobj=True).result()

        self.assertEqual(result.get_counts(circuit), {'0001': 1024})
