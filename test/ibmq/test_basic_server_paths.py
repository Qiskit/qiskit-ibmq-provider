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

from datetime import datetime, timedelta

from qiskit.compiler import assemble, transpile
from qiskit.providers.jobstatus import JobStatus
from qiskit.test.reference_circuits import ReferenceCircuits

from qiskit.providers.ibmq import least_busy
from ..decorators import requires_providers
from ..ibmqtestcase import IBMQTestCase
from ..utils import most_busy_backend, cancel_job


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

    def test_job_submission(self):
        """Test submitting a job."""
        for _desc, provider in self.providers.items():
            with self.subTest(provider=provider):
                backend = least_busy(provider.backends())
                circuit = transpile(self._qc, backend, seed_transpiler=self.seed)
                qobj = assemble(circuit, backend, shots=1)
                job = backend.run(qobj, validate_qobj=True)

                # Fetch the results.
                result = job.result()
                self.assertTrue(result.success)

                # Fetch the qobj.
                qobj_downloaded = job.qobj()
                self.assertEqual(qobj_downloaded, qobj.to_dict())

    def test_job_status_and_properties(self):
        """Test the status and properties of a job."""
        for _desc, provider in self.providers.items():
            with self.subTest(provider=provider):
                backend = most_busy_backend(provider)
                circuit = transpile(self._qc, backend, seed_transpiler=self.seed)
                qobj = assemble(circuit, backend, shots=1)
                job = backend.run(qobj, validate_qobj=True)

                self.assertTrue(job.status())
                self.assertTrue(job.properties())
                cancel_job(job, verify=True)

    def test_retrieving_jobs(self):
        """Test retrieving jobs with filters."""
        backend_name = 'ibmq_qasm_simulator'
        past_month = datetime.now() - timedelta(days=30)
        past_month_str = past_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        db_filter = {
            'backend.name': backend_name,
            'status': {'regexp': '^ERROR'}
        }
        for _desc, provider in self.providers.items():
            jobs = provider.backends.jobs(limit=5, end_datetime=past_month, db_filter=db_filter)
            # Ensure the jobs match the filter.
            for job in jobs:
                job_id = job.job_id()
                provider_job = {'provider': provider, 'job': job_id}
                job_backend_name = job.backend().name()
                with self.subTest(provider_job=provider_job):
                    self.assertEqual(job.backend().name(), backend_name,
                                     'Job {} backend name should be "{}", but it is "{}".'
                                     .format(job_id, job_backend_name, backend_name))
                    self.assertEqual(job.status(), JobStatus.ERROR,
                                     'Job {} status should be "{}", but it is "{}".'
                                     .format(job_id, JobStatus.ERROR, job.status()))
                    self.assertTrue(job.creation_date() <= past_month_str,
                                    'Job {} creation date "{}" is not less than '
                                    'or equal to the past month "{}".'
                                    .format(job_id, job.creation_date(), past_month_str))

    def test_devices_properties_and_defaults(self):
        """Test the properties and defaults for devices."""
        for _desc, provider in self.providers.items():
            for backend in provider.backends():
                provider_backend = {'provider': provider, 'backend': backend}
                with self.subTest(provider_backend=provider_backend):
                    properties = backend.properties()
                    if backend.configuration().simulator:
                        self.assertIsNone(properties)
                    else:
                        self.assertIsNotNone(properties)

                    defaults = backend.defaults()
                    if backend.configuration().open_pulse:
                        self.assertIsNotNone(defaults)
                    else:
                        self.assertIsNone(defaults)

    def test_devices_status_and_job_limit(self):
        """Test the status and job limit for devices."""
        for desc, provider in self.providers.items():
            for backend in provider.backends():
                provider_backend = {'provider': provider, 'backend': backend}
                with self.subTest(provider_backend=provider_backend):
                    self.assertTrue(backend.status())
                    job_limit = backend.job_limit()
                    if desc == 'public_provider':
                        self.assertEqual(job_limit.maximum_jobs, 5)
                    self.assertTrue(job_limit)
