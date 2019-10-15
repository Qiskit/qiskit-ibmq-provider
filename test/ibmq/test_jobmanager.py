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

"""Tests for the JobManager."""
import copy

from qiskit import QuantumCircuit
from qiskit.providers.ibmq.jobmanager import JobManager
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq import least_busy
from qiskit.providers import JobError
from qiskit.compiler import transpile

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, run_on_staging


class TestJobManager(IBMQTestCase):
    """Tests for IBMQFactory `enable_account()`."""

    def setUp(self):
        self._qc = QuantumCircuit(2, 2)
        self._qc.h(0)
        self._qc.cx(0, 1)
        self._qc.measure([0, 1], [0, 1])

        self._jm = JobManager()

    @requires_provider
    def test_split_circuits(self, provider):
        """Test having circuits split into multiple jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_circs = backend.configuration().max_experiments

        circs = []
        for _ in range(max_circs+2):
            circs.append(self._qc)
        job_count = self._jm.run(circs, backend=backend)
        results = self._jm.result()
        statuses = self._jm.status()

        self.assertEqual(job_count, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(s is JobStatus.DONE for s in statuses))

    @run_on_staging
    def test_split_circuits_device(self, provider):
        """Test having circuits split into multiple jobs for a device."""
        backend = least_busy(provider.backends(simulator=False))
        max_circs = backend.configuration().max_experiments

        circs = []
        for _ in range(max_circs+2):
            circs.append(self._qc)
        job_count = self._jm.run(circs, backend=backend)
        results = self._jm.result()
        statuses = self._jm.status()

        self.assertEqual(job_count, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(s is JobStatus.DONE for s in statuses))

    @requires_provider
    def test_no_split_circuits(self, provider):
        """Test running all circuits in a single job."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_circs = backend.configuration().max_experiments

        circs = []
        for _ in range(int(max_circs/2)):
            circs.append(self._qc)
        job_count = self._jm.run(circs, backend=backend)
        results = self._jm.result()
        statuses = self._jm.status()

        self.assertEqual(job_count, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(statuses), 1)

    @requires_provider
    def test_custom_split_circuits(self, provider):
        """Test having circuits split with custom slices."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        job_count = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        results = self._jm.result()
        statuses = self._jm.status()

        self.assertEqual(job_count, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(statuses), 2)

    @requires_provider
    def test_result(self, provider):
        """Test getting results for multiple jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        results = self._jm.result()
        jobs = self._jm.jobs()

        self.assertEqual(len(results), 2)
        for i, result in enumerate(results):
            self.assertIsNotNone(result)
            self.assertDictEqual(result.get_counts(0), jobs[i].result().get_counts(0))

    @requires_provider
    def test_job_report(self, provider):
        """Test job report."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = self._jm.jobs()
        report = self._jm.report()
        print(report)
        for job in jobs:
            self.assertIn(job.job_id(), report)

    @requires_provider
    def test_skipped_result(self, provider):
        """Test one of jobs has no result."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_circs = backend.configuration().max_experiments

        circs = []
        for _ in range(max_circs+2):
            circs.append(self._qc)
        self._jm.run(circs, backend=backend)
        jobs = self._jm.jobs()
        cjob = jobs[0]
        cancelled = False
        for _ in range(2):
            # Try twice in case job is not in a cancellable state
            try:
                cancelled = cjob.cancel()
                if cancelled:
                    break
            except JobError:
                pass

        results = self._jm.result()
        statuses = self._jm.status()
        if cancelled:
            self.assertTrue(statuses[0] is JobStatus.CANCELLED)
            self.assertIsNone(
                results[0], "Job {} cancelled but result is not None.".format(cjob.job_id()))
        else:
            self.log.warning("Unable to cancel job %s", cjob.job_id())

    @requires_provider
    def test_skipped_status(self, provider):
        """Test one of jobs has no status."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = self._jm.jobs()
        jobs[1]._job_id = 'BAD_ID'
        statuses = self._jm.status()
        self.assertIsNone(statuses[1])

    @requires_provider
    def test_job_qobjs(self, provider):
        """Test retrieving qobjs for the jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = self._jm.jobs()
        self._jm.result()
        for i, qobj in enumerate(self._jm.qobj()):
            rjob = provider.backends.retrieve_job(jobs[i].job_id())
            self.assertDictEqual(qobj.__dict__, rjob.qobj().__dict__)

    @run_on_staging
    def test_error_message(self, provider):
        """Test error message report."""
        backend = least_busy(provider.backends(simulator=False))

        bad_qc = copy.deepcopy(self._qc)
        circs = [transpile(self._qc, backend=backend), bad_qc]
        self._jm.run(circs, backend=backend, max_experiments_per_job=1, skip_transpile=True)

        results = self._jm.result()
        self.assertIsNone(results[1])

        error_report = self._jm.error_message()
        self.assertIsNotNone(error_report)
        print("JobManager.error_message(): \n{}".format(error_report))
        print("\nJobManager.report(): \n{}".format(self._jm.report()))
