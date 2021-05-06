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

from unittest import mock
import copy

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import transpile, assemble
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.aer.noise import NoiseModel

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, requires_device


class TestIbmqQasmSimulator(IBMQTestCase):
    """Test IBM Quantum QASM Simulator."""

    @requires_provider
    def setUp(self, provider):
        """Initial test setup."""
        # pylint: disable=arguments-differ
        super().setUp()
        self.provider = provider
        self.sim_backend = self.provider.get_backend('ibmq_qasm_simulator')

    def test_execute_one_circuit_simulator_online(self):
        """Test execute_one_circuit_simulator_online."""
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        qc = QuantumCircuit(qr, cr, name='qc')
        qc.h(qr[0])
        qc.measure(qr[0], cr[0])
        circs = transpile(qc, backend=self.sim_backend, seed_transpiler=73846087)
        shots = 1024
        job = self.sim_backend.run(circs, shots=shots)
        result = job.result()
        counts = result.get_counts(qc)
        target = {'0': shots / 2, '1': shots / 2}
        threshold = 0.1 * shots
        self.assertDictAlmostEqual(counts, target, threshold)

    def test_execute_several_circuits_simulator_online(self):
        """Test execute_several_circuits_simulator_online."""
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
        circs = transpile([qcr1, qcr2], backend=self.sim_backend, seed_transpiler=73846087)
        job = self.sim_backend.run(circs, shots=shots)
        result = job.result()
        counts1 = result.get_counts(qcr1)
        counts2 = result.get_counts(qcr2)
        target1 = {'00': shots / 4, '01': shots / 4,
                   '10': shots / 4, '11': shots / 4}
        target2 = {'00': shots / 2, '11': shots / 2}
        threshold = 0.1 * shots
        self.assertDictAlmostEqual(counts1, target1, threshold)
        self.assertDictAlmostEqual(counts2, target2, threshold)

    def test_online_qasm_simulator_two_registers(self):
        """Test online_qasm_simulator_two_registers."""
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
        circs = transpile([qcr1, qcr2], self.sim_backend, seed_transpiler=8458)
        job = self.sim_backend.run(circs, shots=1024)
        result = job.result()
        result1 = result.get_counts(qcr1)
        result2 = result.get_counts(qcr2)
        self.assertEqual(result1, {'00 01': 1024})
        self.assertEqual(result2, {'10 00': 1024})

    def test_conditional_operation(self):
        """Test conditional operation."""
        qr = QuantumRegister(4)
        cr = ClassicalRegister(4)
        circuit = QuantumCircuit(qr, cr)
        circuit.x(qr[0])
        circuit.x(qr[2])
        circuit.measure(qr[0], cr[0])
        circuit.x(qr[0]).c_if(cr, 1)

        result = self.sim_backend.run(transpile(circuit, backend=self.sim_backend),
                                      validate_qobj=True).result()
        self.assertEqual(result.get_counts(circuit), {'0001': 1024})

    def test_new_sim_method(self):
        """Test new simulator methods."""
        def _new_submit(qobj, *args, **kwargs):
            # pylint: disable=unused-argument
            self.assertEqual(qobj.config.method, 'extended_stabilizer',
                             f"qobj header={qobj.header}")
            return mock.MagicMock()

        backend = copy.deepcopy(self.sim_backend)
        backend._configuration._data['simulation_method'] = 'extended_stabilizer'
        backend._submit_job = _new_submit

        circ = transpile(ReferenceCircuits.bell(), backend=backend)
        backend.run(circ, header={'test': 'circuits'})
        qobj = assemble(circ, backend=backend, header={'test': 'qobj'})
        backend.run(qobj)

    def test_new_sim_method_no_overwrite(self):
        """Test custom method option is not overwritten."""
        def _new_submit(qobj, *args, **kwargs):
            # pylint: disable=unused-argument
            self.assertEqual(qobj.config.method, 'my_method', f"qobj header={qobj.header}")
            return mock.MagicMock()

        backend = copy.deepcopy(self.sim_backend)
        backend._configuration._data['simulation_method'] = 'extended_stabilizer'
        backend._submit_job = _new_submit

        circ = transpile(ReferenceCircuits.bell(), backend=backend)
        backend.run(circ, method='my_method', header={'test': 'circuits'})
        qobj = assemble(circ, backend=backend, method='my_method', header={'test': 'qobj'})
        backend.run(qobj)

    @requires_device
    def test_simulator_with_noise_model(self, backend):
        """Test using simulator with a noise model."""
        noise_model = NoiseModel.from_backend(backend)
        result = self.sim_backend.run(
            transpile(ReferenceCircuits.bell(), backend=self.sim_backend),
            noise_model=noise_model).result()
        self.assertTrue(result)
