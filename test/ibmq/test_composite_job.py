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

"""Tests for the IBMQCompositeJob."""

import re
import copy
import time
from inspect import getfullargspec, isfunction
import uuid
from concurrent.futures import wait
from datetime import datetime, timedelta

from qiskit import QuantumCircuit
from qiskit import transpile
from qiskit.result import Result

from qiskit.providers.ibmq.managed.ibmqjobmanager import IBMQJobManager
from qiskit.providers.ibmq.managed.managedresults import ManagedResults
from qiskit.providers.ibmq.managed import managedjob
from qiskit.providers.ibmq.managed.exceptions import (
    IBMQJobManagerJobNotFound, IBMQManagedResultDataNotAvailable, IBMQJobManagerInvalidStateError)
from qiskit.providers.jobstatus import JobStatus
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.job.exceptions import IBMQJobFailureError
from qiskit.providers.ibmq.job import IBMQCompositeJob

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider
from ..fake_account_client import (BaseFakeAccountClient, CancelableFakeJob,
                                   JobSubmitFailClient, BaseFakeJob, FailedFakeJob,
                                   JobTimeoutClient)


class TestIBMQCompositeJob(IBMQTestCase):
    """Tests for IBMQCompositeJob."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.sim_backend = provider.get_backend('ibmq_qasm_simulator')
        cls.last_week = datetime.now() - timedelta(days=7)

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self._qc = ReferenceCircuits.bell()
        # self._jm = IBMQJobManager()
        self._fake_api_backend = None
        self._fake_api_provider = None

    def tearDown(self):
        """Tear down."""
        super().tearDown()
        if self._fake_api_backend:
            self._fake_api_backend._api_client.tear_down()
        # Restore provider backends since we cannot deep copy provider.
        self.provider.backend._provider = self.provider

    @property
    def fake_api_backend(self):
        """Setup a backend instance with fake API client."""
        if not self._fake_api_backend:
            self._fake_api_backend = copy.copy(self.sim_backend)
            self._fake_api_provider = copy.copy(self.provider)
            self._fake_api_provider._api_client = self._fake_api_backend._api_client \
                = BaseFakeAccountClient()
            self._fake_api_backend._provider = self._fake_api_provider
            self._fake_api_provider.backend._provider = self._fake_api_provider
            self._fake_api_backend._configuration.max_experiments = 10
        return self._fake_api_backend

    @property
    def fake_api_provider(self):
        """Setup a provider instance with fake API client."""
        if not self._fake_api_provider:
            _ = self.fake_api_backend
        return self._fake_api_provider

    def test_split_circuits(self):
        """Test having circuits split into multiple jobs."""
        max_circs = self.fake_api_backend.configuration().max_experiments

        circs = []
        for _ in range(max_circs+2):
            circs.append(self._qc)
        job_set = self.fake_api_backend.run(circs)
        result = job_set.result()

        self.assertEqual(len(job_set.sub_jobs()), 2)
        self.assertEqual(len(result.results), max_circs+2)

    def test_custom_split_circuits(self):
        """Test having circuits split with custom slices."""
        job_set = self.fake_api_backend.run([self._qc]*2, max_circuits_per_job=1)
        self.assertEqual(len(job_set.sub_jobs()), 2)

    def test_job_report(self):
        """Test job report."""
        job_set = self.fake_api_backend.run([self._qc]*2, max_circuits_per_job=1)
        job_set.block_for_submit()

        report = job_set.report()
        for sub_job in job_set.sub_jobs():
            self.assertIn(sub_job.job_id(), report)

    def test_status_initializing(self):
        pass

    def test_status_validating(self):
        pass

    def test_status_running(self):
        pass

    def test_status_queued(self):
        pass

    def test_status_cancelled(self):
        pass

    def test_status_done(self):
        pass

    def test_status_error(self):
        pass

    def test_job_circuits(self):
        pass

    def test_job_backend_options(self):
        pass

    def test_job_header(self):
        pass

    def test_error_message_one(self):
        """Test error message report when one job failed."""
        self.fake_api_backend._api_client = \
            BaseFakeAccountClient(job_class=[BaseFakeJob, FailedFakeJob])
        self.fake_api_provider._api_client = self.fake_api_backend._api_client

        job_set = self.fake_api_backend.run([self._qc]*4, max_circuits_per_job=2)
        error_report = job_set.error_message()
        self.assertIsNotNone(error_report)
        self.assertEqual(job_set.status(), JobStatus.ERROR)
        bad_job = job_set.sub_jobs()[1]
        self.assertIsNotNone(
            re.search(f"Circuits 2-3: Job {bad_job.job_id()} failed: " +
                      r".+ Error code: \d{4}", error_report), f"Error report: {error_report}")

    def test_error_message_all(self):
        """Test error message report when all jobs failed."""
        self.fake_api_backend._api_client = \
            BaseFakeAccountClient(job_class=FailedFakeJob)
        self.fake_api_provider._api_client = self.fake_api_backend._api_client

        job_set = self.fake_api_backend.run([self._qc]*4, max_circuits_per_job=2)
        error_report = job_set.error_message()
        self.assertIsNotNone(error_report)
        for idx, job in enumerate(job_set.sub_jobs()):
            self.assertIsNotNone(
                re.search(f"Circuits {idx*2}-{idx*2+1}: Job {job.job_id()} failed: " +
                          r".+ Error code: \d{4}", error_report), f"Error report: {error_report}")

    def test_async_submit_exception(self):
        """Test asynchronous job submit failed."""
        self.fake_api_backend._api_client = JobSubmitFailClient(max_fail_count=1)

        job_set = self.fake_api_backend.run([self._qc]*2, max_circuits_per_job=1)
        job_set.wait_for_final_state()
        self.assertEqual(job_set.status(), JobStatus.ERROR)
        with self.assertRaises(IBMQJobFailureError):
            job_set.result()
        self.assertIn("Circuits 0-0: Job submit failed", job_set.error_message())
        report = job_set.report()
        self.assertIn("Failed jobs: 1", report)
        self.assertIn("Successful jobs: 1", report)
        self.assertIn("Error submitting job", report)
        self.assertIn("Status: JobStatus.DONE", report)

    def test_share_job_in_project(self):
        """Test sharing managed jobs within a project."""
        job_set = self.fake_api_backend.run([self._qc]*2, max_circuits_per_job=1,
                                            job_share_level="project")
        for job in job_set.sub_jobs():
            self.assertEqual(job.share_level(), 'project')

    def test_job_limit(self):
        """Test reaching job limit."""
        job_limit = 5
        self.fake_api_backend._api_client = BaseFakeAccountClient(
            job_limit=job_limit, job_class=CancelableFakeJob)
        self.fake_api_provider._api_client = self.fake_api_backend._api_client

        job_set = None
        try:
            with self.assertLogs(managedjob.logger, 'WARNING'):
                job_set = self._jm.run([self._qc]*(job_limit+2),
                                       backend=self.fake_api_backend, max_experiments_per_job=1)
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

    def test_job_limit_timeout(self):
        """Test reaching job limit."""
        job_limit = 5
        self.fake_api_backend._api_client = JobTimeoutClient(
            job_limit=job_limit, max_fail_count=1)
        self.fake_api_provider._api_client = self.fake_api_backend._api_client

        job_set = None
        try:
            job_set = self._jm.run([self._qc]*(job_limit+2),
                                   backend=self.fake_api_backend, max_experiments_per_job=1)
            last_mjobs = job_set._managed_jobs[-2:]
            for _ in range(10):
                if all(mjob.job for mjob in last_mjobs):
                    break
            self.assertTrue(all(job.job_id() for job in job_set.jobs()))
        finally:
            # Cancel all jobs.
            for mjob in job_set.managed_jobs():
                if mjob.job is not None:
                    mjob.cancel()
                elif job_set._job_submit_lock.locked():
                    job_set._job_submit_lock.release()
            wait([mjob.future for mjob in job_set.managed_jobs()], timeout=5)

    def test_job_tags_replace(self):
        """Test updating job tags by replacing the job set's existing tags."""
        initial_job_tags = [uuid.uuid4().hex]
        job_set = self._jm.run([self._qc]*2, backend=self.fake_api_backend,
                               max_experiments_per_job=1, job_tags=initial_job_tags)

        # Wait for jobs to be submitted.
        while JobStatus.INITIALIZING in job_set.statuses():
            time.sleep(1)

        tag_prefix = uuid.uuid4().hex
        replacement_tags = ['{}_new_tag_{}'.format(tag_prefix, i) for i in range(2)]
        _ = job_set.update_tags(replacement_tags=replacement_tags)

        for job in job_set.jobs():
            job.refresh()
            self.assertEqual(set(job.tags()), set(replacement_tags + [job_set._id_long]))

    def test_job_tags_remove(self):
        """Test updating job tags by removing the job set's existing tags."""
        initial_job_tags = [uuid.uuid4().hex]
        job_set = self._jm.run([self._qc] * 2, backend=self.fake_api_backend,
                               max_experiments_per_job=1, job_tags=initial_job_tags)

        # Wait for jobs to be submitted.
        while JobStatus.INITIALIZING in job_set.statuses():
            time.sleep(1)

        initial_job_tags_with_id_long = initial_job_tags + [job_set._id_long]

        # Update the job tags
        _ = job_set.update_tags(removal_tags=initial_job_tags_with_id_long)

        for job in job_set.jobs():
            job.refresh()
            self.assertEqual(job.tags(), [job_set._id_long])

    def test_index_by_number(self):
        """Test indexing results by number."""
        max_per_job = 5
        job_set = self._jm.run([self._qc]*max_per_job*2, backend=self.fake_api_backend,
                               max_experiments_per_job=max_per_job)
        result_manager = job_set.results()
        jobs = job_set.jobs()

        for i in [0, max_per_job-1, max_per_job+1]:
            with self.subTest(i=i):
                job_index = int(i / max_per_job)
                exp_index = i % max_per_job
                self.assertEqual(result_manager.get_counts(i),
                                 jobs[job_index].result().get_counts(exp_index))

    def test_index_by_name(self):
        """Test indexing results by name."""
        max_per_job = 5
        circs = []
        for i in range(max_per_job*2+1):
            new_qc = copy.deepcopy(self._qc)
            new_qc.name = "test_qc_{}".format(i)
            circs.append(new_qc)
        job_set = self._jm.run(circs, backend=self.fake_api_backend,
                               max_experiments_per_job=max_per_job)
        result_manager = job_set.results()
        jobs = job_set.jobs()

        for i in [1, max_per_job, len(circs)-1]:
            with self.subTest(i=i):
                job_index = int(i / max_per_job)
                exp_index = i % max_per_job
                self.assertEqual(result_manager.get_counts(circs[i].name),
                                 jobs[job_index].result().get_counts(exp_index))

    def test_index_out_of_range(self):
        """Test result index out of range."""
        job_set = self._jm.run([self._qc], backend=self.fake_api_backend)
        result_manager = job_set.results()
        with self.assertRaises(IBMQJobManagerJobNotFound):
            result_manager.get_counts(1)

    def test_skipped_result(self):
        """Test one of jobs has no result."""
        self.fake_api_backend._api_client = BaseFakeAccountClient(
            job_class=[BaseFakeJob, CancelableFakeJob])

        job_set = self._jm.run([self._qc]*2, backend=self.fake_api_backend,
                               max_experiments_per_job=1)
        jobs = job_set.jobs()
        jobs[1].cancel()

        result_manager = job_set.results()
        with self.assertRaises(IBMQManagedResultDataNotAvailable):
            result_manager.get_counts(1)

    def test_combine_results(self):
        """Test converting ManagedResult to Result."""
        max_per_job = 5
        job_set = self._jm.run([self._qc]*max_per_job*2, backend=self.fake_api_backend,
                               max_experiments_per_job=max_per_job)
        result_manager = job_set.results()
        combined_result = result_manager.combine_results()

        for i in range(max_per_job*2):
            self.assertEqual(result_manager.get_counts(i), combined_result.get_counts(i))

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
        del managed_results_methods['combine_results']
        for ignore_meth in ['to_dict', 'from_dict']:
            result_methods.pop(ignore_meth, None)

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


class TestIBMQCompositeJobIntegration(IBMQTestCase):

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.sim_backend = provider.get_backend('ibmq_qasm_simulator')
        cls._qc = transpile(ReferenceCircuits.bell(), backend=cls.sim_backend)
        cls.last_week = datetime.now() - timedelta(days=7)

    def test_retrieve_job(self):
        """Test retrieving a composite job."""
        tags = ['test_retrieve_job_set']

        circs_counts = [3, 4]
        for count in circs_counts:
            with self.subTest(count=count):
                job_set = self.sim_backend.run([self._qc]*count, max_circuits_per_job=2,
                                               job_tags=tags)
                job_set.block_for_submit()
                self.assertEqual(job_set.tags(), tags)

                rjob_set = self.sim_backend.retrieve_job(job_set.job_id())
                self.assertIsInstance(rjob_set, IBMQCompositeJob)
                self.assertEqual(rjob_set.job_id(), job_set.job_id())
                self.assertEqual(len(rjob_set.sub_jobs()), len(job_set.sub_jobs()))
                self.assertEqual({rsub.job_id() for rsub in rjob_set.sub_jobs()},
                                 {sub.job_id() for sub in job_set.sub_jobs()})
                self.assertEqual(rjob_set.tags(), job_set.tags())
                self.assertEqual(job_set.result().to_dict(), rjob_set.result().to_dict())

    def test_jobs(self):
        """Test retrieving a composite job using jobs."""
        job_tags = [uuid.uuid4().hex]
        job_set = self.sim_backend.run([self._qc]*2, max_circuits_per_job=1,
                                       job_tags=job_tags)
        job_set.block_for_submit()
        circ_job = self.sim_backend.run(self._qc, job_tags=job_tags)

        rjobs = self.provider.backend.jobs(job_tags=job_tags, start_datetime=self.last_week)
        self.assertEqual(len(rjobs), 2)
        for job in rjobs:
            if job.job_id().startswith(IBMQCompositeJob._id_prefix):
                self.assertEqual(job.job_id(), job_set.job_id())
                self.assertEqual(len(job.sub_jobs()), len(job_set.sub_jobs()))
                self.assertEqual({rsub.job_id() for rsub in job.sub_jobs()},
                                 {sub.job_id() for sub in job_set.sub_jobs()})
            else:
                self.assertEqual(job.job_id(), circ_job.job_id())
