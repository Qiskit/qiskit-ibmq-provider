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
from datetime import datetime, timedelta, timezone
from dateutil import tz

from qiskit import QuantumCircuit
from qiskit import transpile
from qiskit.result import Result
from qiskit.exceptions import QiskitError
from qiskit.circuit.random import random_circuit
from qiskit.providers.models import BackendProperties

from qiskit.providers.ibmq.managed.ibmqjobmanager import IBMQJobManager
from qiskit.providers.ibmq.managed.managedresults import ManagedResults
from qiskit.providers.ibmq.managed import managedjob
from qiskit.providers.ibmq.managed.exceptions import (
    IBMQJobManagerJobNotFound, IBMQManagedResultDataNotAvailable, IBMQJobManagerInvalidStateError)
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.job.exceptions import (IBMQJobFailureError, IBMQJobInvalidStateError,
                                                  IBMQJobNotFoundError, IBMQJobTimeoutError)
from qiskit.providers.ibmq.job import IBMQCompositeJob
from qiskit.providers.ibmq.apiconstants import ApiJobStatus

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider
from ..fake_account_client import (BaseFakeAccountClient, CancelableFakeJob,
                                   JobSubmitFailClient, BaseFakeJob, FailedFakeJob,
                                   JobTimeoutClient, FixedStatusFakeJob, MissingFieldFakeJob)


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
        self.fake_backend = copy.copy(self.sim_backend)
        self.fake_provider = copy.copy(self.provider)
        self._set_fake_client(BaseFakeAccountClient())
        self.fake_backend._provider = self.fake_provider
        self.fake_provider.backend._provider = self.fake_provider
        self.fake_backend._configuration.max_experiments = 5

    def tearDown(self):
        """Tear down."""
        super().tearDown()
        self.fake_backend._api_client.tear_down()
        # Restore provider backends since we cannot deep copy provider.
        # self.provider.backend._provider = self.provider

    def _set_fake_client(self, fake_client):
        self.fake_backend._api_client = fake_client
        self.fake_provider._api_client = fake_client

    def test_split_circuits(self):
        """Test having circuits split into multiple jobs."""
        max_circs = self.fake_backend.configuration().max_experiments

        circs = []
        for _ in range(max_circs+2):
            circs.append(self._qc)
        job_set = self.fake_backend.run(circs)
        result = job_set.result()

        self.assertEqual(len(job_set.sub_jobs()), 2)
        self.assertEqual(len(result.results), max_circs+2)
        self.assertTrue(job_set.job_id().startswith(IBMQCompositeJob._id_prefix))

    def test_custom_split_circuits(self):
        """Test having circuits split with custom slices."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        self.assertEqual(len(job_set.sub_jobs()), 2)

    def test_job_report(self):
        """Test job report."""
        job_classes = [BaseFakeJob, FailedFakeJob, CancelableFakeJob, CancelableFakeJob,
                       FixedStatusFakeJob]
        job_count = len(job_classes)
        self._set_fake_client(BaseFakeAccountClient(
            job_class=job_classes,
            job_kwargs={'fixed_status': ApiJobStatus.VALIDATING}))

        job_set = self.fake_backend.run([self._qc] * len(job_classes), max_circuits_per_job=1)
        job_set.sub_jobs()[2].cancel()
        job_set.sub_jobs()[0].wait_for_final_state()

        for detailed in [True, False]:
            with self.subTest(detailed=detailed):
                report = job_set.report(detailed=detailed)
                self.assertIn(job_set.job_id(), report)
                self.assertIn(f"Total jobs: {job_count}", report)
                for stat in ['Successful', 'Failed', 'Cancelled', 'Running', 'Pending']:
                    self.assertIn(f"{stat} jobs: 1", report)
                if detailed:
                    for sub_job in job_set.sub_jobs():
                        self.assertIn(sub_job.job_id(), report)
                    for i in range(job_count):
                        self.assertIn(f"Circuits {i}-{i}:", report)
                        self.assertIn(f"Job index: {i}", report)
                    for stat in [JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELLED, JobStatus.RUNNING,
                                 JobStatus.VALIDATING]:
                        self.assertIn(f"Status: {stat}", report)
                else:
                    for sub_job in job_set.sub_jobs():
                        self.assertNotIn(sub_job.job_id(), report)

    def test_job_pending_status(self):
        """Test pending and running status."""
        sub_tests = [(ApiJobStatus.VALIDATING, JobStatus.VALIDATING, 'Pending'),
                     (ApiJobStatus.RUNNING, JobStatus.RUNNING, 'Running'),
                     (ApiJobStatus.QUEUED, JobStatus.QUEUED, 'Pending')]

        for api_status, job_status, report_text in sub_tests:
            with self.subTest(status=job_status):
                self._set_fake_client(BaseFakeAccountClient(
                    job_class=[BaseFakeJob, FixedStatusFakeJob],
                    job_kwargs={'fixed_status': api_status}))

                job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
                stat_job = job_set.sub_jobs()[1]
                while stat_job.status() != job_status:
                    time.sleep(1)
                time.sleep(0.5)  # Wait for other job to advance.
                self.assertEqual(job_set.status(), job_status)
                self.assertNotEqual(job_set.sub_jobs()[0].status(), job_status)
                self.assertEqual(stat_job.status(), job_status)
                report = job_set.report()
                self.assertIn(f"{report_text} jobs: 1", report)
                self.assertIsNotNone(
                    re.search(rf"Job ID: {stat_job.job_id()}\s*Status: {job_status}", report),
                    report)

    def test_status_done(self):
        """Test job status of completed."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        job_set.wait_for_final_state()
        self.assertEqual(job_set.status(), JobStatus.DONE)
        for sub_job in job_set.sub_jobs():
            self.assertEqual(sub_job.status(), JobStatus.DONE)
        self.assertIn("Successful jobs: 2", job_set.report())

    def test_job_circuits(self):
        """Test job circuits."""
        circs = []
        for _ in range(3):
            circs.append(random_circuit(num_qubits=2, depth=3, measure=True))
        circs_copied = circs.copy()
        job_set = self.fake_backend.run(circs, max_circuits_per_job=1)
        job_circuits = job_set.circuits()
        self.assertEqual(job_circuits, circs_copied)
        for i, sub_job in enumerate(job_set.sub_jobs()):
            self.assertEqual(sub_job.circuits()[0], circs_copied[i])

    def test_job_backend_options(self):
        """Test getting backend options."""
        custom_options = {'shots': 100, 'memory': True}
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        **custom_options)
        self.assertLessEqual(custom_options.items(), job_set.backend_options().items())
        job_set.block_for_submit()
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertLessEqual(custom_options.items(), rjob_set.backend_options().items())

    def test_job_header(self):
        """Test getting job header."""
        custom_header = {'test': 'test_job_header'}
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        header=custom_header)
        self.assertLessEqual(custom_header.items(), job_set.header().items())
        job_set.block_for_submit()
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertLessEqual(custom_header.items(), rjob_set.header().items())

    def test_job_backend(self):
        """Test getting job backend."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        self.assertEqual(job_set.backend().name(), self.fake_backend.name())
        job_set.block_for_submit()
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertEqual(rjob_set.backend().name(), self.fake_backend.name())

    def test_job_name(self):
        """Test job name."""
        custom_name = 'batman'
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        job_name=custom_name)
        self.assertEqual(job_set.name(), custom_name)
        job_set.block_for_submit()
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertEqual(rjob_set.name(), custom_name)

    def test_job_name_update(self):
        """Test changing the name associated with a job."""
        new_name = 'robin'
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        job_name='batman')
        job_set.update_name(new_name)
        self.assertEqual(job_set.name(), new_name)
        job_set.block_for_submit()
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertEqual(rjob_set.name(), new_name)

    def test_job_properties(self):
        """Test job properties."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        self.assertIsInstance(job_set.properties(), BackendProperties)

    def test_multiple_job_properties(self):
        """Test multiple job properties."""
        self._set_fake_client(BaseFakeAccountClient(props_count=2))

        job_set = self.fake_backend.run([self._qc] * 3, max_circuits_per_job=1)
        props = job_set.properties()
        self.assertIsInstance(props, list)
        self.assertEqual(len(props), 2)
        self.assertTrue(all(isinstance(prop, BackendProperties) for prop in props))

    def test_error_message_one(self):
        """Test error message when one job failed."""
        failure_types = ['validation', 'partial', 'result']
        for fail_type in failure_types:
            with self.subTest(fail_type=fail_type):
                self._set_fake_client(
                    BaseFakeAccountClient(job_class=[BaseFakeJob, FailedFakeJob],
                                          job_kwargs={'failure_type': fail_type}))

                job_set = self.fake_backend.run([self._qc] * 4, max_circuits_per_job=2)
                error_msg = job_set.error_message()
                self.assertIsNotNone(error_msg)
                self.assertEqual(job_set.status(), JobStatus.ERROR)
                self.assertNotEqual(job_set.sub_jobs()[0].status, JobStatus.ERROR)
                bad_job = job_set.sub_jobs()[1]
                self.assertIsNotNone(
                    re.search(f"Circuits 2-3: Job {bad_job.job_id()} failed: ", error_msg),
                    f"Error msg: {error_msg}")
                if fail_type == 'partial':
                    self.assertIn('Experiment 1:', error_msg)
                else:
                    self.assertIsNotNone(re.search(r"Error code: \d{4}", error_msg),
                                         f"Error msg: {error_msg}")

    def test_error_message_all(self):
        """Test error message report when all jobs failed."""
        self._set_fake_client(BaseFakeAccountClient(job_class=FailedFakeJob))

        job_set = self.fake_backend.run([self._qc] * 4, max_circuits_per_job=2)
        error_msg = job_set.error_message()
        self.assertIsNotNone(error_msg)
        for idx, job in enumerate(job_set.sub_jobs()):
            self.assertIsNotNone(
                re.search(f"Circuits {idx*2}-{idx*2+1}: Job {job.job_id()} failed: " +
                          r".+ Error code: \d{4}", error_msg), f"Error msg: {error_msg}")

    def test_async_submit_exception(self):
        """Test asynchronous job submit failed."""
        self.fake_backend._api_client = JobSubmitFailClient(failed_indexes=1)

        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
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

        result = job_set.result(partial=True)
        self.assertFalse(result.success)
        self.assertFalse(result.results[0].success)
        self.assertFalse(result.results[0].data.to_dict())

    def test_share_job_in_project(self):
        """Test sharing managed jobs within a project."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        job_share_level="project")
        for job in job_set.sub_jobs():
            self.assertEqual(job.share_level(), 'project')

    def test_job_limit(self):
        """Test reaching job limit."""
        job_limit = 3
        self._set_fake_client(BaseFakeAccountClient(
            job_limit=job_limit, job_class=CancelableFakeJob))

        job_set = None
        try:
            job_set = self.fake_backend.run(
                [self._qc]*(job_limit+2), max_circuits_per_job=1)

            # Wait for first 5 jobs to be submitted.
            max_loop = 5
            while len(job_set.sub_jobs(block_for_submit=False)) < job_limit and max_loop:
                time.sleep(0.5)
                max_loop -= 1
            self.assertGreater(max_loop, 0)
            self.assertEqual(job_set.status(), JobStatus.INITIALIZING)
            report = job_set.report()
            self.assertIsNotNone(
                re.search(r"index: 3\s+Status: Job not yet submitted.*"
                          r"index: 4\s+Status: Job not yet submitted", report, re.DOTALL), report)

            for job in job_set.sub_jobs(block_for_submit=False):
                job.cancel()
            time.sleep(0.5)
            self.assertNotIn('Job not yet submitted', job_set.report())
        finally:
            job_set.cancel()

    def test_job_limit_timeout(self):
        """Test timing out while waiting for old job to finish."""
        job_limit = 3
        self._set_fake_client(JobTimeoutClient(job_limit=job_limit, max_fail_count=1))

        job_set = None
        try:
            job_set = self.fake_backend.run(
                [self._qc]*(job_limit+2), max_circuits_per_job=1)
            self.assertEqual(job_set.status(), JobStatus.INITIALIZING)
            job_set.wait_for_final_state(timeout=60)
        finally:
            job_set.cancel()

    def test_job_tags_replace(self):
        """Test updating job tags by replacing existing tags."""
        initial_job_tags = [uuid.uuid4().hex]
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        job_tags=initial_job_tags)
        job_set.block_for_submit()
        tag_prefix = uuid.uuid4().hex
        replacement_tags = ['{}_new_tag_{}'.format(tag_prefix, i) for i in range(2)]
        job_set.update_tags(replacement_tags=replacement_tags)
        for job in job_set.sub_jobs():
            job.refresh()
            job_set_tags = \
                {tag for tag in job.tags() if tag.startswith(IBMQCompositeJob._tag_prefix)}
            self.assertEqual(set(job.tags())-job_set_tags, set(replacement_tags), job.tags())
            self.assertIn(job_set.job_id(), job_set_tags, job.tags())
            self.assertEqual(len(job_set_tags), 2, job.tags())

    def test_skipped_result(self):
        """Test one of the jobs has no result."""
        sub_tests = [CancelableFakeJob, FailedFakeJob]
        for job_class in sub_tests:
            with self.subTest(job_class=job_class):
                self.fake_backend._api_client = BaseFakeAccountClient(
                    job_class=[BaseFakeJob, job_class])

                job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
                job_set.block_for_submit()
                if job_class == CancelableFakeJob:
                    job_set.sub_jobs()[1].cancel()
                result = job_set.result(partial=True)
                self.assertEqual(len(result.results), 2)
                self.assertFalse(result.success)
                self.assertTrue(result.results[0].success)
                self.assertFalse(result.results[1].success)
                self.assertTrue(result.get_counts(0))
                with self.assertRaises(QiskitError):
                    result.get_counts(1)

    def test_partial_result(self):
        """Test one of the circuits has no result."""
        self.fake_backend._api_client = BaseFakeAccountClient(
            job_class=[BaseFakeJob, FailedFakeJob], job_kwargs={'failure_type': 'partial'})
        job_set = self.fake_backend.run([self._qc] * 4, max_circuits_per_job=2)
        job_set.block_for_submit()
        result = job_set.result(partial=True)
        self.assertEqual(len(result.results), 4)
        self.assertFalse(result.success)
        self.assertTrue(all(res.success for res in result.results[:3]))
        self.assertFalse(result.results[3].success)
        with self.assertRaises(QiskitError):
            result.get_counts(3)

    def test_job_result(self):
        """Test job result."""
        max_per_job = 3
        job_set = self.fake_backend.run([self._qc] * max_per_job * 2,
                                        max_circuits_per_job=max_per_job)
        result = job_set.result()
        self.assertTrue(result.success)
        for i in range(max_per_job*2):
            self.assertEqual(
                result.get_counts(i),
                job_set.sub_jobs()[int(i/max_per_job)].result().get_counts(i % max_per_job))
            self.assertTrue(result.results[i].success)

    def test_cancel(self):
        """Test job cancellation."""
        self.fake_backend._api_client = BaseFakeAccountClient(
            job_class=[BaseFakeJob, CancelableFakeJob])

        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        job_set.block_for_submit()
        job_set.cancel()
        self.assertEqual(job_set.status(), JobStatus.CANCELLED)
        with self.assertRaises(IBMQJobInvalidStateError):
            job_set.result(partial=False)

    def test_refresh(self):
        """Test refreshing job data."""
        pass

    def test_creation_date(self):
        """Test retrieving creation date."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        creation_date = job_set.creation_date()
        self.assertTrue(creation_date)
        self.assertIsNotNone(creation_date.tzinfo)
        self.assertEqual(creation_date, job_set.sub_jobs()[0].creation_date())

    def test_time_per_step_done(self):
        """Test retrieving time per step when job is done."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        job_set.wait_for_final_state()
        time_per_step = job_set.time_per_step()
        self.assertTrue(time_per_step)
        self.assertIn('COMPLETED', time_per_step)
        self.assertEqual(time_per_step['CREATING'], job_set.creation_date())
        status_samples = ['CREATING', 'QUEUED', 'RUNNING', 'COMPLETED']
        for i in range(0, len(status_samples)-1):
            self.assertLessEqual(time_per_step[status_samples[i]],
                                 time_per_step[status_samples[i+1]])

    def test_time_per_step_running(self):
        """Test retrieving time per step when job is running."""
        self._set_fake_client(
            BaseFakeAccountClient(job_class=[BaseFakeJob, FixedStatusFakeJob],
                                  job_kwargs={'fixed_status': ApiJobStatus.RUNNING}))
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        while job_set.status() != JobStatus.RUNNING:
            time.sleep(1)
        job_set.sub_jobs()[0].wait_for_final_state()
        time_per_step = job_set.time_per_step()
        self.assertTrue(time_per_step)
        self.assertIn('RUNNING', time_per_step)
        self.assertNotIn('COMPLETED', time_per_step)
        self.assertEqual(time_per_step['CREATING'], job_set.creation_date())
        status_samples = ['CREATING', 'QUEUED', 'RUNNING']
        for i in range(0, len(status_samples)-1):
            self.assertLessEqual(time_per_step[status_samples[i]],
                                 time_per_step[status_samples[i+1]])

    def test_time_per_step_error(self):
        """Test retrieving time per step when job failed."""
        self._set_fake_client(BaseFakeAccountClient(job_class=[BaseFakeJob, FailedFakeJob]))
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        job_set.wait_for_final_state()
        self.assertEqual(job_set.status(), JobStatus.ERROR)
        time_per_step = job_set.time_per_step()
        self.assertTrue(time_per_step)
        self.assertIn('ERROR_VALIDATING_JOB', time_per_step)
        self.assertNotIn('COMPLETED', time_per_step)
        self.assertEqual(time_per_step['CREATING'], job_set.creation_date())
        status_samples = ['CREATING', 'VALIDATING', 'ERROR_VALIDATING_JOB']
        for i in range(0, len(status_samples)-1):
            self.assertLessEqual(time_per_step[status_samples[i]],
                                 time_per_step[status_samples[i+1]])

    def test_queue_info(self):
        """Test retrieving queue information."""
        ts1 = datetime.now() + timedelta(minutes=5)
        ts2 = datetime.now() + timedelta(minutes=10)
        sub_tests = [  # Queue positions and expected position/completion time.
            ([2, 5], (5, ts2)),
            ([2, None], None),
            ([None, 5], None),
            ([None, None], None)]

        for positions, expected in sub_tests:
            with self.subTest(positions=positions):
                self._set_fake_client(BaseFakeAccountClient(
                    job_class=FixedStatusFakeJob, job_kwargs={'fixed_status': ApiJobStatus.QUEUED},
                    queue_positions=positions, est_completion=[ts1, ts2]))
                job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
                while job_set.status() != JobStatus.QUEUED:
                    time.sleep(1)
                queue_info = job_set.queue_info()
                if expected is not None:
                    self.assertIsNotNone(queue_info)
                    self.assertEqual(queue_info.position, expected[0])
                    ts_local = expected[1].replace(tzinfo=timezone.utc)
                    ts_local = ts_local.astimezone(tz.tzlocal())
                    self.assertEqual(queue_info.estimated_complete_time, ts_local)
                else:
                    self.assertIsNone(queue_info)

    def test_scheduling_mode(self):
        """Test job scheduling mode."""
        sub_tests = [('fairshare', 'fairshare'),
                     ('dedicated', 'dedicated'),
                     ('dedicated_once', 'fairshare')]
        for mode, expected in sub_tests:
            with self.subTest(mode=mode):
                self._set_fake_client(BaseFakeAccountClient(run_mode=mode))
                job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
                while job_set.status() not in [JobStatus.RUNNING, JobStatus.DONE]:
                    time.sleep(1)
                self.assertEqual(job_set.scheduling_mode(), expected)

    def test_client_version(self):
        """Test job client version information."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        job_set.block_for_submit()
        client_version = job_set.client_version
        self.assertTrue(client_version)
        self.assertEqual(client_version, job_set.sub_jobs()[0].client_version)
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertEqual(rjob_set.client_version, client_version)

    def test_experiment_id(self):
        """Test job experiment id."""
        experiment_id = 12345
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1,
                                        experiment_id=experiment_id)
        job_set.block_for_submit()
        self.assertTrue(job_set.experiment_id)
        self.assertEqual(job_set.experiment_id, experiment_id)
        rjob_set = self.fake_backend.retrieve_job(job_set.job_id())
        self.assertEqual(rjob_set.experiment_id, experiment_id)

    def test_retrieve_job_error(self):
        """Test retrieving an invalid job."""
        with self.assertRaises(IBMQJobNotFoundError):
            self.fake_backend.retrieve_job(IBMQCompositeJob._id_prefix + '1234')

    def test_missing_required_fields(self):
        """Test response data is missing required fields."""
        self._set_fake_client(BaseFakeAccountClient(job_class=[BaseFakeJob, MissingFieldFakeJob]))
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        job_set.wait_for_final_state()
        self.assertEqual(job_set.status(), JobStatus.ERROR)
        self.assertIn("Unexpected return value received", job_set.error_message())

    def test_refresh_job_result(self):
        """Test re-retrieving job result via refresh."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        result = job_set.result()

        self.assertTrue(result)
        cached_result = copy.deepcopy(result.to_dict())
        result.results[0].header.name = 'modified_result'
        self.assertNotEqual(cached_result, result.to_dict())

        # Re-retrieve result via refresh.
        result = job_set.result(refresh=True)
        self.assertDictEqual(cached_result, result.to_dict())
        self.assertNotEqual(result.results[0].header.name, 'modified_result')

    def test_wait_for_final_state(self):
        """Test waiting for job to reach final state."""

        def final_state_callback(c_job_id, c_status, c_job, **kwargs):
            """Job status query callback function."""
            self.assertEqual(c_job_id, job_set.job_id())
            self.assertNotIn(c_status, JOB_FINAL_STATES)
            self.assertEqual(c_job.job_id(), job_set.job_id())
            self.assertIn('queue_info', kwargs)

            queue_info = kwargs.pop('queue_info', None)
            callback_info['called'] = True

            if wait_time is None:
                # Look for status change.
                data = {'status': c_status, 'queue_info': queue_info}
                self.assertNotEqual(data, callback_info['last data'])
                callback_info['last data'] = data
            else:
                # Check called within wait time.
                if callback_info['last call time'] and job_set._status not in JOB_FINAL_STATES:
                    self.assertAlmostEqual(
                        time.time() - callback_info['last call time'], wait_time, delta=0.2)
                callback_info['last call time'] = time.time()

        wait_args = [2, None]
        self._set_fake_client(BaseFakeAccountClient(job_kwargs={'progress_time': 1}))

        for wait_time in wait_args:
            with self.subTest(wait_time=wait_time):
                # Put callback data in a dictionary to make it mutable.
                callback_info = {'called': False, 'last call time': 0.0, 'last data': {}}
                job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
                job_set.wait_for_final_state(timeout=10, wait=wait_time,
                                             callback=final_state_callback)
                self.assertEqual(job_set.status(), JobStatus.DONE)
                self.assertTrue(callback_info['called'])

    def test_wait_for_final_state_timeout(self):
        """Test waiting for job to reach final state times out."""
        job_set = self.fake_backend.run([self._qc] * 2, max_circuits_per_job=1)
        with self.assertRaises(IBMQJobTimeoutError):
            job_set.wait_for_final_state(timeout=0.1)

    def test_retry_failed_submit(self):
        """Test retrying failed job submit."""
        max_circs = self.fake_backend.configuration().max_experiments
        circs = []
        count = 3
        for i in range(max_circs*(count-1)+1):
            circs.append(random_circuit(num_qubits=2, depth=3, measure=True))
        sub_tests = [[0], [1, 2], [0, 2]]

        for failed_index in sub_tests:
            with self.subTest(failed_index=failed_index):
                self._set_fake_client(JobSubmitFailClient(failed_indexes=failed_index))
                job_set = self.fake_backend.run(circs)
                job_set.wait_for_final_state()
                self.assertEqual(job_set.status(), JobStatus.ERROR)
                good_indexes = set(range(count)) - set(failed_index)
                self.assertEqual(len(job_set.sub_jobs()), len(good_indexes))
                good_ids = {job.job_id() for job in job_set.sub_jobs()}

                job_set.rerun_failed()
                job_set.wait_for_final_state()
                self.assertEqual(job_set.status(), JobStatus.DONE)
                self.assertEqual(len(job_set.sub_jobs()), count)
                self.assertTrue(good_ids.issubset({job.job_id() for job in job_set.sub_jobs()}))
                circ_idx = 0
                for sub_job in job_set.sub_jobs():
                    for job_circ in sub_job.circuits():
                        self.assertEqual(job_circ, circs[circ_idx])
                        circ_idx += 1
                self.assertEqual(job_set.circuits(), circs)

    def test_retry_failed_jobs(self):
        """Test retrying failed jobs."""

    def test_sub_job(self):
        pass


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
                circs = []
                for i in range(count):
                    circs.append(random_circuit(num_qubits=2, depth=3, measure=True))
                circs = transpile(circs, backend=self.sim_backend)
                job_set = self.sim_backend.run(circs, max_circuits_per_job=2, job_tags=tags)
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
                job_circuits = job_set.circuits()
                rjob_circuits = rjob_set.circuits()
                self.assertEqual(len(job_circuits), count)
                self.assertEqual(len(job_circuits), len(rjob_circuits))
                for i in range(len(job_circuits)):
                    self.assertEqual(job_circuits[i], rjob_circuits[i])

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

    def test_retrieve_job_missing_subjobs(self):
        pass

    def test_partial_result(self):
        # with simulator
        pass