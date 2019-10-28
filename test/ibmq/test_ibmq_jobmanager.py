# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the IBMQJobManager."""
import copy
from unittest import mock
import time

from qiskit import QuantumCircuit
from qiskit.providers.ibmq.managed.ibmqjobmanager import IBMQJobManager
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq import least_busy
from qiskit.providers import JobError
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.exceptions import IBMQBackendError
from qiskit.compiler import transpile

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, run_on_staging
from ..fake_account_client import BaseFakeAccountClient


class TestIBMQJobManager(IBMQTestCase):
    """Tests for IBMQJobManager."""

    def setUp(self):
        self._qc = QuantumCircuit(2, 2)
        self._qc.h(0)
        self._qc.cx(0, 1)
        self._qc.measure([0, 1], [0, 1])

        self._jm = IBMQJobManager()

    @requires_provider
    def test_split_circuits(self, provider):
        """Test having circuits split into multiple jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_circs = backend.configuration().max_experiments
        backend._api = BaseFakeAccountClient()

        circs = []
        for _ in range(max_circs+2):
            circs.append(self._qc)
        job_set = self._jm.run(circs, backend=backend)
        results = job_set.results()
        statuses = job_set.statuses()

        self.assertEqual(len(results), 2)
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(s is JobStatus.DONE for s in statuses))

    @requires_provider
    def test_no_split_circuits(self, provider):
        """Test running all circuits in a single job."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_circs = backend.configuration().max_experiments
        backend._api = BaseFakeAccountClient()

        circs = []
        for _ in range(int(max_circs/2)):
            circs.append(self._qc)
        job_set = self._jm.run(circs, backend=backend)
        results = job_set.results()
        statuses = job_set.statuses()

        self.assertEqual(len(results), 1)
        self.assertEqual(len(statuses), 1)

    @requires_provider
    def test_custom_split_circuits(self, provider):
        """Test having circuits split with custom slices."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        results = job_set.results()
        statuses = job_set.statuses()

        self.assertEqual(len(results), 2)
        self.assertEqual(len(statuses), 2)

    @requires_provider
    def test_result(self, provider):
        """Test getting results for multiple jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        results = job_set.results()
        jobs = job_set.jobs()

        self.assertEqual(len(results), 2)
        for i, result in enumerate(results):
            self.assertIsNotNone(result)
            self.assertDictEqual(result.get_counts(0), jobs[i].result().get_counts(0))

    @requires_provider
    def test_job_report(self, provider):
        """Test job report."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = job_set.jobs()
        report = self._jm.report()
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
        job_set = self._jm.run(circs, backend=backend)
        jobs = job_set.jobs()
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

        results = job_set.results()
        statuses = job_set.statuses()
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
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = job_set.jobs()
        jobs[1]._job_id = 'BAD_ID'
        statuses = job_set.statuses()
        self.assertIsNone(statuses[1])

    @requires_provider
    def test_job_qobjs(self, provider):
        """Test retrieving qobjs for the jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = job_set.jobs()
        job_set.results()
        for i, qobj in enumerate(job_set.qobjs()):
            rjob = provider.backends.retrieve_job(jobs[i].job_id())
            self.assertDictEqual(qobj.__dict__, rjob.qobj().__dict__)

    @run_on_staging
    def test_error_message(self, provider):
        """Test error message report."""
        backend = least_busy(provider.backends(simulator=False))

        bad_qc = copy.deepcopy(self._qc)
        circs = [transpile(self._qc, backend=backend), bad_qc]
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)

        jobs = job_set.jobs()
        results = job_set.results(timeout=300)
        self.assertIsNone(results[1])

        error_report = job_set.error_messages()
        self.assertIsNotNone(error_report)
        self.assertIn(jobs[1].job_id(), error_report)

    @requires_provider
    def test_async_submit_exception(self, provider):
        """Test asynchronous job submit failed."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        circs = []
        for _ in range(2):
            circs.append(self._qc)
        with mock.patch.object(IBMQBackend, 'run',
                               side_effect=[IBMQBackendError("Kaboom!"), mock.DEFAULT]):
            job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        self.assertIsNone(job_set.jobs()[0])
        self.assertIsNotNone(job_set.jobs()[1])

        # Make sure results() and statuses() don't fail
        job_set.results()
        job_set.statuses()

    @requires_provider
    def test_multiple_job_sets(self, provider):
        """Test submitting multiple sets of jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        qc2 = QuantumCircuit(1, 1)
        qc2.h(0)
        qc2.measure([0], [0])

        job_set1 = self._jm.run([self._qc, self._qc], backend=backend, max_experiments_per_job=1)
        job_set2 = self._jm.run([qc2], backend=backend, max_experiments_per_job=1)

        id1 = {job.job_id() for job in job_set1.jobs()}
        id2 = {job.job_id() for job in job_set2.jobs()}
        self.assertTrue(id1.isdisjoint(id2))

    @requires_provider
    def test_retrieve_job_sets(self, provider):
        """Test retrieving a set of jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()
        name = str(time.time()).replace('.', '')

        self._jm.run([self._qc], backend=backend, max_experiments_per_job=1)
        job_set = self._jm.run([self._qc, self._qc], backend=backend,
                               name=name, max_experiments_per_job=1)
        rjob_set = self._jm.job_sets(name=name)[0]
        self.assertEqual(job_set, rjob_set)
