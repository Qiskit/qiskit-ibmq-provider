# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Integration tests."""

import time

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, execute
from qiskit.result import Result
from qiskit.compiler import transpile
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, requires_device, requires_private_provider


class TestIBMQIntegration(IBMQTestCase):
    """Integration tests."""

    seed = 42

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.sim_backend = provider.get_backend('ibmq_qasm_simulator')

    def setUp(self):
        super().setUp()
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        self._qc1 = QuantumCircuit(qr, cr, name='qc1')
        self._qc2 = QuantumCircuit(qr, cr, name='qc2')
        self._qc1.measure(qr[0], cr[0])
        self._qc2.x(qr[0])
        self._qc2.measure(qr[0], cr[0])

    def test_ibmq_result_fields(self):
        """Test components of a result from a remote simulator."""
        remote_result = execute(self._qc1, self.sim_backend).result()
        self.assertIsInstance(remote_result, Result)
        self.assertEqual(remote_result.backend_name, self.sim_backend.name())
        self.assertIsInstance(remote_result.job_id, str)
        self.assertEqual(remote_result.status, 'COMPLETED')
        self.assertEqual(remote_result.results[0].status, 'DONE')

    @requires_device
    def test_compile_remote(self, backend):
        """Test transpile with a remote backend."""
        qubit_reg = QuantumRegister(2, name='q')
        clbit_reg = ClassicalRegister(2, name='c')
        qc = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)

        circuits = transpile(qc, backend=backend)
        self.assertIsInstance(circuits, QuantumCircuit)

    @requires_device
    def test_compile_two_remote(self, backend):
        """Test transpile with a remote backend on two circuits."""
        qubit_reg = QuantumRegister(2, name='q')
        clbit_reg = ClassicalRegister(2, name='c')
        qc = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)
        qc_extra = QuantumCircuit(qubit_reg, clbit_reg, name="extra")
        qc_extra.measure(qubit_reg, clbit_reg)
        circuits = transpile([qc, qc_extra], backend)
        self.assertIsInstance(circuits[0], QuantumCircuit)
        self.assertIsInstance(circuits[1], QuantumCircuit)

    def test_compile_two_run_remote(self):
        """Test transpile and run two circuits."""
        qubit_reg = QuantumRegister(2, name='q')
        clbit_reg = ClassicalRegister(2, name='c')
        qc = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)
        qc_extra = QuantumCircuit(qubit_reg, clbit_reg, name="extra")
        qc_extra.measure(qubit_reg, clbit_reg)
        circs = transpile([qc, qc_extra], backend=self.sim_backend,
                          seed_transpiler=self.seed)
        job = self.sim_backend.run(circs)
        result = job.result()
        self.assertIsInstance(result, Result)

    def test_execute_two_remote(self):
        """Test executing two circuits on a remote backend."""
        qc = ReferenceCircuits.bell()
        qc_extra = QuantumCircuit(2, 2)
        qc_extra.measure_all()
        job = execute([qc, qc_extra], self.sim_backend, seed_transpiler=self.seed)
        results = job.result()
        self.assertIsInstance(results, Result)

    @requires_private_provider
    def test_private_job(self, provider):
        """Test a private job."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        qc = ReferenceCircuits.bell()
        job = execute(qc, backend=backend)
        self.assertIsNotNone(job.qobj())
        self.assertIsNotNone(job.result())

        # Wait a bit for databases to update.
        time.sleep(2)
        rjob = backend.retrieve_job(job.job_id())

        with self.assertRaises(IBMQJobApiError) as err_cm:
            rjob.qobj()
        self.assertIn('2801', str(err_cm.exception))

        with self.assertRaises(IBMQJobApiError) as err_cm:
            rjob.result()
        self.assertIn('2801', str(err_cm.exception))
