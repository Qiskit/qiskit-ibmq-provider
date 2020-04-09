# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests that hit all the basic server endpoints using both a public and premium provider."""

from qiskit.compiler import assemble, transpile
from qiskit.test import slow_test
from qiskit.test.reference_circuits import ReferenceCircuits

from qiskit.providers.ibmq import least_busy
from ..decorators import requires_providers
from ..ibmqtestcase import IBMQTestCase
from ..utils import cancel_job


class TestBasicServerPaths(IBMQTestCase):
    """Test the basic server endpoints using both a public and premium provider."""

    @classmethod
    @requires_providers
    def setUpClass(cls, providers):
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.providers = providers  # Dict[str, AccountProvider]
        cls._qc = ReferenceCircuits.bell()
        cls.seed = 73846087

    @slow_test
    def test_job_submission(self):
        """Test running a job against a device."""
        for _desc, provider in self.providers.items():
            backend = least_busy(provider.backends(
                simulator=False, filters=lambda b: b.configuration().n_qubits >= 5))
            provider_backend = {'provider': provider, 'backend': backend}
            with self.subTest(provider_backend=provider_backend):
                circuit = transpile(self._qc, backend, seed_transpiler=self.seed)
                qobj = assemble(circuit, backend, shots=1)
                job = backend.run(qobj, validate_qobj=True)

                # Fetch the results.
                result = job.result()
                self.assertTrue(result.success)

                # Fetch the qobj.
                qobj_downloaded = job.qobj()
                self.assertEqual(qobj_downloaded, qobj.to_dict())

    def test_job_backend_properties_and_status(self):
        """Test the backend properties and status of a job."""
        for _desc, provider in self.providers.items():
            backend = provider.backends(
                simulator=False, filters=lambda b: b.configuration().n_qubits >= 5)
            provider_backend = {'provider': provider, 'backend': backend}
            with self.subTest(provider_backend=provider_backend):
                circuit = transpile(self._qc, backend, seed_transpiler=self.seed)
                qobj = assemble(circuit, backend, shots=1)
                job = backend.run(qobj, validate_qobj=True)

                self.assertIsNotNone(job.properties())
                self.assertTrue(job.status())
                cancel_job(job, verify=True)

    def test_retrieving_jobs(self):
        """Test retrieving jobs."""
        backend_name = 'ibmq_qasm_simulator'
        for _desc, provider in self.providers.items():
            with self.subTest(provider=provider):
                job_list = provider.backends.jobs(backend_name=backend_name, limit=5, skip=0)
                self.assertTrue(job_list)

    def test_device_properties_and_defaults(self):
        """Test the properties and defaults for an open pulse device."""
        for _desc, provider in self.providers.items():
            pulse_backends = provider.backends(open_pulse=True, operational=True)
            if not pulse_backends:
                raise self.skipTest('Skipping pulse test since no pulse backend '
                                    'found for provider "{}"'.format(provider))

            pulse_backend = pulse_backends[0]
            provider_backend = {'provider': provider, 'backend': pulse_backend}
            with self.subTest(provider_backend=provider_backend):
                self.assertIsNotNone(pulse_backend.properties())
                self.assertIsNotNone(pulse_backend.defaults())

    def test_device_status_and_job_limit(self):
        """Test the status and job limit for a device."""
        for desc, provider in self.providers.items():
            backend = provider.backends(simulator=False)[0]
            provider_backend = {'provider': provider, 'backend': backend}
            with self.subTest(provider_backend=provider_backend):
                self.assertTrue(backend.status())
                job_limit = backend.job_limit()
                if desc == 'public_provider':
                    self.assertEqual(job_limit.maximum_jobs, 5)
                self.assertTrue(job_limit)
