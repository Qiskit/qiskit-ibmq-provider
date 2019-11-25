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

"""IBMQ provider integration tests (compile and run)."""
from inspect import getfullargspec, isfunction

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.result import Result
from qiskit.execute import execute
from qiskit.compiler import assemble, transpile

from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.ibmqbackendservice import IBMQBackendService
from qiskit.providers.ibmq.managed.managedresults import ManagedResults

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, requires_device


class TestIBMQIntegration(IBMQTestCase):
    """Qiskit's IBMQ Provider integration tests."""

    seed = 42

    def setUp(self):
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        self._qc1 = QuantumCircuit(qr, cr, name='qc1')
        self._qc2 = QuantumCircuit(qr, cr, name='qc2')
        self._qc1.measure(qr[0], cr[0])
        self._qc2.x(qr[0])
        self._qc2.measure(qr[0], cr[0])

    @requires_provider
    def test_ibmq_result_fields(self, provider):
        """Test components of a result from a remote simulator."""
        remote_backend = provider.get_backend(local=False, simulator=True)
        remote_result = execute(self._qc1, remote_backend).result()
        self.assertEqual(remote_result.backend_name, remote_backend.name())
        self.assertIsInstance(remote_result.job_id, str)
        self.assertEqual(remote_result.status, 'COMPLETED')
        self.assertEqual(remote_result.results[0].status, 'DONE')

    @requires_device
    def test_compile_remote(self, backend):
        """Test Compiler remote."""
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
        """Test Compiler remote on two circuits."""
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

    @requires_provider
    def test_compile_run_remote(self, provider):
        """Test Compiler and run remote."""
        backend = provider.get_backend(local=False, simulator=True)

        qubit_reg = QuantumRegister(2, name='q')
        clbit_reg = ClassicalRegister(2, name='c')
        qc = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)
        qobj = assemble(transpile(qc, backend=backend, seed_transpiler=self.seed),
                        backend=backend)
        job = backend.run(qobj)
        result = job.result(timeout=20)
        self.assertIsInstance(result, Result)

    @requires_provider
    def test_compile_two_run_remote(self, provider):
        """Test Compiler and run two circuits."""
        backend = provider.get_backend(local=False, simulator=True)

        qubit_reg = QuantumRegister(2, name='q')
        clbit_reg = ClassicalRegister(2, name='c')
        qc = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)
        qc_extra = QuantumCircuit(qubit_reg, clbit_reg, name="extra")
        qc_extra.measure(qubit_reg, clbit_reg)
        qobj = assemble(transpile([qc, qc_extra], backend=backend, seed_transpiler=self.seed),
                        backend=backend)
        job = backend.run(qobj)
        result = job.result()
        self.assertIsInstance(result, Result)

    @requires_provider
    def test_execute_remote(self, provider):
        """Test Execute remote."""
        backend = provider.get_backend(local=False, simulator=True)

        qubit_reg = QuantumRegister(2)
        clbit_reg = ClassicalRegister(2)
        qc = QuantumCircuit(qubit_reg, clbit_reg)
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)

        job = execute(qc, backend, seed_transpiler=self.seed)
        results = job.result()
        self.assertIsInstance(results, Result)

    @requires_provider
    def test_execute_two_remote(self, provider):
        """Test execute two remote."""
        backend = provider.get_backend(local=False, simulator=True)

        qubit_reg = QuantumRegister(2)
        clbit_reg = ClassicalRegister(2)
        qc = QuantumCircuit(qubit_reg, clbit_reg)
        qc.h(qubit_reg[0])
        qc.cx(qubit_reg[0], qubit_reg[1])
        qc.measure(qubit_reg, clbit_reg)
        qc_extra = QuantumCircuit(qubit_reg, clbit_reg)
        qc_extra.measure(qubit_reg, clbit_reg)
        job = execute([qc, qc_extra], backend, seed_transpiler=self.seed)
        results = job.result()
        self.assertIsInstance(results, Result)

    def test_ensure_backend_jobs_signature(self):
        """Test `IBMQBackend.jobs` signature is similar to `IBMQBackendService.jobs`

        The signature of `IBMQBackend.jobs` is similar to the signature of
        `IBMQBackendService.jobs` if its parameter list is a subset of the
        parameter list of `IBMQBackendService.jobs`.
        """
        backend_cls = IBMQBackend
        backend_service_cls = IBMQBackendService

        # Retrieve parameter lists for both classes.
        backend_jobs_args = getattr(
            getfullargspec(backend_cls.jobs), 'args', [])
        provider_backends_jobs_args = getattr(
            getfullargspec(backend_service_cls.jobs), 'args', [])

        # Ensure parameter lists not empty
        self.assertTrue(backend_jobs_args)
        self.assertTrue(provider_backends_jobs_args)

        if not all(arg in provider_backends_jobs_args for arg in backend_jobs_args):
            # `IBMQBackend.jobs` parameter list not a subset of `IBMQBackendService.jobs`.

            # Get methods fully qualified name, includes class.
            backend_jobs_name = getattr(
                backend_cls.jobs, '__qualname__', str(backend_cls.jobs))
            provider_backend_jobs_name = getattr(
                backend_service_cls.jobs, '__qualname__', str(backend_service_cls.jobs))

            differing_args = set(backend_jobs_args) - set(provider_backends_jobs_args)
            # pylint: disable=duplicate-string-formatting-argument
            raise Exception("`{}` does not match the parameters of `{}`. "
                            "`{}` has the extra parameter(s): {}"
                            .format(backend_jobs_name, provider_backend_jobs_name,
                                    backend_jobs_name, differing_args))

    def test_ibmq_managed_job_signature(self):
        """Test `ManagedResults` and `Result` contain the same public methods.

        Note:
            Aside from ensuring that the two classes contain the same public
            methods, it is also necessary to check that the corresponding
            methods have the same signature.
        """
        result_cls = Result
        managed_results_cls = ManagedResults

        # Get `Result` public methods.
        result_methods = self._get_class_methods(result_cls)
        self.assertTrue(result_methods)

        # Get `ManagedResults` public methods.
        managed_results_methods = self._get_class_methods(managed_results_cls)
        self.assertTrue(managed_results_methods)

        # Ensure `ManagedResults` has the same public methods as `Result`.
        differing_args = set(result_methods.keys()) - set(managed_results_methods.keys())
        self.assertEqual(len(differing_args), 0)

        # Ensure the methods from both classes are compatible.
        for name, method in managed_results_methods.items():
            managed_results_args = getattr(getfullargspec(method), 'args', [])
            result_args = getattr(getfullargspec(result_methods[name]), 'args', [])
            self.assertTrue(managed_results_args)
            self.assertTrue(result_args)
            self.assertEqual(managed_results_args, result_args)

    def _get_class_methods(self, cls):
        """Get public class methods from its namespace.

        Note:
            Since the methods are found using the class itself and not
            and instance, the "methods" are categorized as functions.
            Methods are only bound when they belong to an actual instance.
        """
        cls_methods = {}
        for name, method in cls.__dict__.items():
            if isfunction(method) and not name.startswith('_'):
                cls_methods[name] = method
        return cls_methods
