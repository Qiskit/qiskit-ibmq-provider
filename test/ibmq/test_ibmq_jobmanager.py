# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
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
import time
from inspect import getfullargspec, isfunction
import uuid
from concurrent.futures import wait

from qiskit import QuantumCircuit
from qiskit.result import Result

from qiskit.providers.ibmq.managed.ibmqjobmanager import IBMQJobManager
from qiskit.providers.ibmq.managed.managedjobset import ManagedJobSet
from qiskit.providers.ibmq.managed.managedresults import ManagedResults
from qiskit.providers.ibmq.managed import managedjob
from qiskit.providers.ibmq.managed.exceptions import (
    IBMQJobManagerJobNotFound, IBMQManagedResultDataNotAvailable, IBMQJobManagerInvalidStateError)
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.compiler import transpile, assemble
from qiskit.test.reference_circuits import ReferenceCircuits

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider
from ..fake_account_client import (BaseFakeAccountClient, CancelableFakeJob,
                                   JobSubmitFailClient)
from ..utils import cancel_job


class TestIBMQJobManager(IBMQTestCase):
    """Tests for IBMQJobManager."""

    def setUp(self):
        """Initial test setup."""
        self._qc = ReferenceCircuits.bell()
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
        job_set.results()
        statuses = job_set.statuses()

        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(s is JobStatus.DONE for s in statuses))
        self.assertTrue(len(job_set.jobs()), 2)

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
        self.assertTrue(len(job_set.jobs()), 1)

    @requires_provider
    def test_custom_split_circuits(self, provider):
        """Test having circuits split with custom slices."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        job_set = self._jm.run([self._qc]*2, backend=backend, max_experiments_per_job=1)
        self.assertTrue(len(job_set.jobs()), 2)

    @requires_provider
    def test_job_report(self, provider):
        """Test job report."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        job_set = self._jm.run([self._qc]*2, backend=backend, max_experiments_per_job=1)
        jobs = job_set.jobs()
        report = self._jm.report()
        for job in jobs:
            self.assertIn(job.job_id(), report)

    @requires_provider
    def test_skipped_status(self, provider):
        """Test one of jobs has no status."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        job_set = self._jm.run([self._qc]*2, backend=backend, max_experiments_per_job=1)
        jobs = job_set.jobs()
        jobs[1]._job_id = 'BAD_ID'
        statuses = job_set.statuses()
        self.assertIsNone(statuses[1])

    @requires_provider
    def test_job_qobjs(self, provider):
        """Test retrieving qobjs for the jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()
        provider._api = backend._api
        qc2 = QuantumCircuit(1, 1)
        qc2.x(0)
        qc2.measure(0, 0)
        circs = [self._qc, qc2]

        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
        jobs = job_set.jobs()
        job_set.results()
        for i, qobj in enumerate(job_set.qobjs()):
            rjob = provider.backends.retrieve_job(jobs[i].job_id())
            self.maxDiff = None  # pylint: disable=invalid-name
            self.assertDictEqual(qobj.to_dict(), rjob.qobj().to_dict())

    @requires_provider
    def test_error_message(self, provider):
        """Test error message report."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        # Create a bad job.
        qc_new = transpile(self._qc, backend)
        qobj = assemble([qc_new, qc_new], backend=backend)
        qobj.experiments[1].instructions[1].name = 'bad_instruction'
        job = backend.run(qobj, validate_qobj=True)

        job_set = self._jm.run([self._qc]*4, backend=backend, max_experiments_per_job=2)
        job_set.results()
        job_set.managed_jobs()[1].job = job

        error_report = job_set.error_messages()
        self.assertIsNotNone(error_report)
        self.assertIn(job.job_id(), error_report)

    @requires_provider
    def test_async_submit_exception(self, provider):
        """Test asynchronous job submit failed."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = JobSubmitFailClient(max_fail_count=1)

        job_set = self._jm.run([self._qc]*2, backend=backend, max_experiments_per_job=1)
        self.assertTrue(any(job is None for job in job_set.jobs()))
        self.assertTrue(any(job is not None for job in job_set.jobs()))

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
    def test_retrieve_job_sets_by_name(self, provider):
        """Test retrieving job sets by name."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()
        name = str(time.time()).replace('.', '')

        job_set = self._jm.run([self._qc]*2, backend=backend,
                               name=name, max_experiments_per_job=1)
        rjob_set = self._jm.job_sets(name=name)[0]
        self.assertEqual(job_set, rjob_set)

    @requires_provider
    def test_retrieve_job_set(self, provider):
        """Test retrieving a set of jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        tags = ['test_retrieve_job_set']

        circs_counts = [3, 4]
        for count in circs_counts:
            with self.subTest(count=count):
                circs = []
                for i in range(count):
                    new_qc = copy.deepcopy(self._qc)
                    new_qc.name = "test_qc_{}".format(i)
                    circs.append(new_qc)

                job_set = self._jm.run(circs, backend=backend,
                                       max_experiments_per_job=2, job_tags=tags)
                self.assertEqual(job_set.tags(), tags)
                # Wait for jobs to be submitted.
                while JobStatus.INITIALIZING in job_set.statuses():
                    time.sleep(1)

                rjob_set = IBMQJobManager().retrieve_job_set(
                    job_set_id=job_set.job_set_id(), provider=provider)
                self.assertEqual({job.job_id() for job in job_set.jobs()},
                                 {rjob.job_id() for rjob in rjob_set.jobs()},
                                 "Unexpected jobs retrieved. Job set id used was {}.".format(
                                     job_set.job_set_id()))
                self.assertEqual(rjob_set.tags(), job_set.tags())
                self.assertEqual(len(rjob_set.qobjs()), len(job_set.qobjs()))
                self.log.info("Job set report:\n%s", rjob_set.report())

                mjobs = job_set.managed_jobs()
                for index, rmjob in enumerate(rjob_set.managed_jobs()):
                    mjob = mjobs[index]
                    self.assertEqual(rmjob.start_index, mjob.start_index)
                    self.assertEqual(rmjob.end_index, mjob.end_index)
                    for exp_index, exp in enumerate(rmjob.job.qobj().experiments):
                        self.assertEqual(exp.header.name,
                                         mjob.job.qobj().experiments[exp_index].header.name)
                rjob_set.results()
                self.assertEqual(rjob_set.statuses(), [JobStatus.DONE]*len(job_set.jobs()))

    @requires_provider
    def test_share_job_in_project(self, provider):
        """Test sharing managed jobs within a project."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient()

        job_set = self._jm.run([self._qc]*2, backend=backend, max_experiments_per_job=1,
                               job_share_level="project")
        for job in job_set.jobs():
            job.refresh()
            self.assertEqual(getattr(job, 'share_level'), 'project',
                             "Job {} has incorrect share level".format(job.job_id()))

    @requires_provider
    def test_invalid_job_share_level(self, provider):
        """Test setting a non existent share level for managed jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        self.assertRaises(IBMQJobManagerInvalidStateError, self._jm.run,
                          [self._qc]*2, backend=backend, job_share_level="invalid_job_share_level")

    @requires_provider
    def test_job_tags(self, provider):
        """Test job tags for managed jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        job_tags = [uuid.uuid4().hex]
        job_set = self._jm.run([self._qc]*2, backend=backend, max_experiments_per_job=1,
                               job_tags=job_tags)
        # Wait for jobs to be submitted.
        while JobStatus.INITIALIZING in job_set.statuses():
            time.sleep(1)
        # TODO No need to wait for job to run once api is fixed
        while any(status not in JOB_FINAL_STATES + (JobStatus.RUNNING,)
                  for status in job_set.statuses()):
            time.sleep(0.5)

        rjobs = provider.backends.jobs(job_tags=job_tags)
        self.assertEqual({job.job_id() for job in job_set.jobs()},
                         {rjob.job_id() for rjob in rjobs},
                         "Unexpected jobs retrieved. Job tag used was {}".format(job_tags))
        self.assertEqual(job_set.tags(), job_tags)

    @requires_provider
    def test_job_limit(self, provider):
        """Test reaching job limit."""
        job_limit = 5
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend._api = BaseFakeAccountClient(
            job_limit=job_limit, job_class=CancelableFakeJob)
        provider._api = backend._api

        circs = transpile([self._qc]*(job_limit+2), backend=backend)
        job_set = None
        try:
            with self.assertLogs(managedjob.logger, 'WARNING'):
                job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=1)
                time.sleep(1)

            # There should be 5 done and 2 running futures.
            running_futures = [mjob.future for mjob in job_set.managed_jobs()
                               if mjob.future.running()]
            max_wait = 6
            while len(running_futures) > 2 and max_wait > 0:
                running_futures = [f for f in running_futures if f.running()]
                time.sleep(0.5)
            self.assertEqual(len(running_futures), 2)

            for mjob in job_set.managed_jobs():
                if mjob.job is not None:
                    mjob.cancel()
            self.assertEqual(len(job_set.jobs()), job_limit+2)
            self.assertTrue(all(job_set.jobs()))
        finally:
            # Cancel all submitted jobs first.
            for mjob in job_set.managed_jobs():
                if mjob.job is not None:
                    mjob.cancel()
                elif job_set._job_submit_lock.locked():
                    job_set._job_submit_lock.release()
            wait([mjob.future for mjob in job_set.managed_jobs()], timeout=5)

    @requires_provider
    def test_job_tags_replace(self, provider):
        """Test updating job tags by replacing the job set's existing tags."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        initial_job_tags = [uuid.uuid4().hex]
        job_set = self._jm.run([self._qc] * 2, backend=backend,
                               max_experiments_per_job=1, job_tags=initial_job_tags)

        # Wait for jobs to be submitted.
        while JobStatus.INITIALIZING in job_set.statuses():
            time.sleep(1)

        tag_prefix = uuid.uuid4().hex
        replacement_tags = ['{}_new_tag_{}'.format(tag_prefix, i) for i in range(2)]
        replacement_tags_with_id_long = replacement_tags + [job_set._id_long]

        # Update the job set tags.
        _ = job_set.update_tags(replacement_tags=replacement_tags)

        # Cached results may be returned if quickly retrieving jobs,
        # after an update, so wait some time.
        time.sleep(2)

        # Refresh the jobs in the job set and ensure that the tags were updated correctly.
        job_set.retrieve_jobs(provider, refresh=True)
        for job in job_set.jobs():
            job_id = job.job_id()
            with self.subTest(job_id=job_id):
                self.assertEqual(set(job.tags()), set(replacement_tags_with_id_long),
                                 'Updating the tags for job {} was unsuccessful.'
                                 'The tags are {}, but they should be {}.'
                                 .format(job_id, job.tags(), replacement_tags_with_id_long))

    @requires_provider
    def test_job_tags_remove(self, provider):
        """Test updating job tags by removing the job set's existing tags."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        initial_job_tags = [uuid.uuid4().hex]
        job_set = self._jm.run([self._qc] * 2, backend=backend,
                               max_experiments_per_job=1, job_tags=initial_job_tags)

        # Wait for jobs to be submitted.
        while JobStatus.INITIALIZING in job_set.statuses():
            time.sleep(1)

        initial_job_tags_with_id_long = initial_job_tags + [job_set._id_long]

        # Update the job tags
        _ = job_set.update_tags(removal_tags=initial_job_tags_with_id_long)

        # Cached results may be returned if quickly retrieving jobs,
        # after an update, so wait some time.
        time.sleep(2)

        # Refresh the jobs in the job set and ensure that the job set long id is still present.
        job_set.retrieve_jobs(provider, refresh=True)
        for job in job_set.jobs():
            job_id = job.job_id()
            with self.subTest(job_id=job_id):
                self.assertEqual(job.tags(), [job_set._id_long],
                                 'Updating the tags for job {} was unsuccessful.'
                                 'The tags are {}, but they should be {}.'
                                 .format(job_id, job.tags(), [job_set._id_long]))


class TestResultManager(IBMQTestCase):
    """Tests for ResultManager."""

    def setUp(self):
        """Initial test setup."""
        self._qc = ReferenceCircuits.bell()
        self._jm = IBMQJobManager()

    @requires_provider
    def test_index_by_number(self, provider):
        """Test indexing results by number."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_per_job = 5
        job_set = self._jm.run([self._qc]*max_per_job*2, backend=backend,
                               max_experiments_per_job=max_per_job)
        result_manager = job_set.results()
        jobs = job_set.jobs()

        for i in [0, max_per_job-1, max_per_job+1]:
            with self.subTest(i=i):
                job_index = int(i / max_per_job)
                exp_index = i % max_per_job
                self.assertEqual(result_manager.get_counts(i),
                                 jobs[job_index].result().get_counts(exp_index))

    @requires_provider
    def test_index_by_name(self, provider):
        """Test indexing results by name."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        max_per_job = 5
        circs = []
        for i in range(max_per_job*2+1):
            new_qc = copy.deepcopy(self._qc)
            new_qc.name = "test_qc_{}".format(i)
            circs.append(new_qc)
        job_set = self._jm.run(circs, backend=backend, max_experiments_per_job=max_per_job)
        result_manager = job_set.results()
        jobs = job_set.jobs()

        for i in [1, max_per_job, len(circs)-1]:
            with self.subTest(i=i):
                job_index = int(i / max_per_job)
                exp_index = i % max_per_job
                self.assertEqual(result_manager.get_counts(circs[i].name),
                                 jobs[job_index].result().get_counts(exp_index))

    @requires_provider
    def test_index_out_of_range(self, provider):
        """Test result index out of range."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        job_set = self._jm.run([self._qc], backend=backend)
        result_manager = job_set.results()
        with self.assertRaises(IBMQJobManagerJobNotFound):
            result_manager.get_counts(1)

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
        cjob = jobs[1]
        cancelled = cancel_job(cjob)

        result_manager = job_set.results()
        if cancelled:
            with self.assertRaises(IBMQManagedResultDataNotAvailable,
                                   msg="IBMQManagedResultDataNotAvailable not "
                                       "raised for job {}".format(cjob.job_id())):
                result_manager.get_counts(max_circs)
        else:
            self.log.warning("Unable to cancel job %s", cjob.job_id())

    def test_ibmq_managed_results_signature(self):
        """Test ``ManagedResults`` and ``Result`` contain the same public methods.

        Note:
            Aside from ensuring the two classes contain the same public
            methods, it is also necessary to check that the corresponding
            methods have the same signature.
        """
        result_methods = self._get_class_methods(Result)
        self.assertTrue(result_methods)

        managed_results_methods = self._get_class_methods(ManagedResults)
        self.assertTrue(managed_results_methods)

        # Ensure both classes share the *exact* same public methods.
        self.assertEqual(result_methods.keys(), managed_results_methods.keys())

        # Ensure the signature for the public methods from both classes are compatible.
        for name, method in managed_results_methods.items():
            managed_results_params = getattr(getfullargspec(method), 'args', [])
            result_params = getattr(getfullargspec(result_methods[name]), 'args', [])
            self.assertTrue(managed_results_params)
            self.assertTrue(result_params)
            # pylint: disable=duplicate-string-formatting-argument
            self.assertEqual(result_params, managed_results_params,
                             "The signatures for method `{}` differ. "
                             "`Result.{}` params = {} "
                             "`ManagedResults.{}` params = {}."
                             .format(name, name, managed_results_params,
                                     name, result_params))

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
