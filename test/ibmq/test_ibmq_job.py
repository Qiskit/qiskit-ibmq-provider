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

"""IBMQJob Test."""

import time
import copy
from datetime import datetime, timedelta
from unittest import SkipTest, mock, skip
from threading import Thread, Event

from dateutil import tz

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.test import slow_test
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.compiler import transpile
from qiskit.result import Result
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.providers.ibmq import least_busy
from qiskit.providers.ibmq.apiconstants import ApiJobStatus, API_JOB_FINAL_STATES
from qiskit.providers.ibmq.ibmqbackend import IBMQRetiredBackend
from qiskit.providers.ibmq.exceptions import IBMQBackendError, IBMQBackendApiError
from qiskit.providers.ibmq.utils.utils import api_status_to_job_status
from qiskit.providers.ibmq.job.exceptions import IBMQJobTimeoutError
from qiskit.providers.ibmq.utils.converters import local_to_utc
from qiskit.providers.ibmq.api.rest.job import Job as RestJob
from qiskit.providers.ibmq.api.exceptions import RequestsApiError

from ..ibmqtestcase import IBMQTestCase
from ..decorators import (requires_provider, requires_device)
from ..utils import (most_busy_backend, cancel_job,
                     submit_job_bad_shots, submit_and_cancel, submit_job_one_bad_instr)
from ..fake_account_client import BaseFakeAccountClient, CancelableFakeJob


class TestIBMQJob(IBMQTestCase):
    """Test ibmqjob module."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.sim_backend = provider.get_backend('ibmq_qasm_simulator')
        cls.bell = transpile(ReferenceCircuits.bell(), cls.sim_backend)
        cls.sim_job = cls.sim_backend.run(cls.bell, validate_qobj=True)
        cls.last_month = datetime.now() - timedelta(days=30)

    @slow_test
    @requires_device
    def test_run_device(self, backend):
        """Test running in a real device."""
        shots = 8192
        job = backend.run(transpile(ReferenceCircuits.bell(), backend=backend),
                          validate_qobj=True, shots=shots)

        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result = job.result()
        counts_qx = result.get_counts(0)
        counts_ex = {'00': shots / 2, '11': shots / 2}
        self.assertDictAlmostEqual(counts_qx, counts_ex, shots * 0.2)

        # Test fetching the job properties, as this is a real backend and is
        # guaranteed to have them.
        self.assertIsNotNone(job.properties())

    def test_run_multiple_simulator(self):
        """Test running multiple jobs in a simulator."""
        num_qubits = 16
        qr = QuantumRegister(num_qubits, 'qr')
        cr = ClassicalRegister(num_qubits, 'cr')
        qc = QuantumCircuit(qr, cr)
        for i in range(num_qubits - 1):
            qc.cx(qr[i], qr[i + 1])
        qc.measure(qr, cr)
        num_jobs = 5
        job_array = [self.sim_backend.run(transpile([qc] * 20), validate_qobj=True, shots=2048)
                     for _ in range(num_jobs)]
        timeout = 30
        start_time = time.time()
        while True:
            check = sum(
                [job.status() is JobStatus.RUNNING for job in job_array])
            if check >= 2:
                self.log.info('found %d simultaneous jobs', check)
                break
            if all([job.status() is JobStatus.DONE for job in job_array]):
                # done too soon? don't generate error
                self.log.warning('all jobs completed before simultaneous jobs '
                                 'could be detected')
                break
            for job in job_array:
                self.log.info('%s %s %s %s', job.status(), job.status() is JobStatus.RUNNING,
                              check, job.job_id())
            self.log.info('-  %s', str(time.time() - start_time))
            if time.time() - start_time > timeout and self.sim_backend.status().pending_jobs <= 5:
                raise TimeoutError('Failed to see multiple running jobs after '
                                   '{0} seconds.'.format(timeout))
            time.sleep(0.2)

        result_array = [job.result() for job in job_array]
        self.log.info('got back all job results')
        # Ensure all jobs have finished.
        self.assertTrue(
            all([job.status() is JobStatus.DONE for job in job_array]))
        self.assertTrue(all([result.success for result in result_array]))

        # Ensure job ids are unique.
        job_ids = [job.job_id() for job in job_array]
        self.assertEqual(sorted(job_ids), sorted(list(set(job_ids))))

    @slow_test
    @requires_device
    def test_run_multiple_device(self, backend):
        """Test running multiple jobs in a real device."""
        num_qubits = 5
        qr = QuantumRegister(num_qubits, 'qr')
        cr = ClassicalRegister(num_qubits, 'cr')
        qc = QuantumCircuit(qr, cr)
        for i in range(num_qubits - 1):
            qc.cx(qr[i], qr[i + 1])
        qc.measure(qr, cr)
        num_jobs = 3
        job_array = [backend.run(transpile(qc, backend=backend), validate_qobj=True)
                     for _ in range(num_jobs)]
        time.sleep(3)  # give time for jobs to start (better way?)
        job_status = [job.status() for job in job_array]
        num_init = sum(
            [status is JobStatus.INITIALIZING for status in job_status])
        num_queued = sum([status is JobStatus.QUEUED for status in job_status])
        num_running = sum(
            [status is JobStatus.RUNNING for status in job_status])
        num_done = sum([status is JobStatus.DONE for status in job_status])
        num_error = sum([status is JobStatus.ERROR for status in job_status])
        self.log.info('number of currently initializing jobs: %d/%d',
                      num_init, num_jobs)
        self.log.info('number of currently queued jobs: %d/%d',
                      num_queued, num_jobs)
        self.log.info('number of currently running jobs: %d/%d',
                      num_running, num_jobs)
        self.log.info('number of currently done jobs: %d/%d',
                      num_done, num_jobs)
        self.log.info('number of errored jobs: %d/%d',
                      num_error, num_jobs)
        self.assertTrue(num_jobs - num_error - num_done > 0)

        # Wait for all the results.
        for job in job_array:
            job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result_array = [job.result() for job in job_array]

        # Ensure all jobs have finished.
        self.assertTrue(
            all([job.status() is JobStatus.DONE for job in job_array]))
        self.assertTrue(all([result.success for result in result_array]))

        # Ensure job ids are unique.
        job_ids = [job.job_id() for job in job_array]
        self.assertEqual(sorted(job_ids), sorted(list(set(job_ids))))

    def test_cancel(self):
        """Test job cancellation."""
        # Find the most busy backend
        backend = most_busy_backend(self.provider)
        submit_and_cancel(backend)

    def test_retrieve_jobs(self):
        """Test retrieving jobs."""
        job_list = self.provider.backend.jobs(
            backend_name=self.sim_backend.name(), limit=5, skip=0, start_datetime=self.last_month)
        self.assertLessEqual(len(job_list), 5)
        for job in job_list:
            self.assertTrue(isinstance(job.job_id(), str))

    def test_retrieve_job(self):
        """Test retrieving a single job."""
        retrieved_job = self.provider.backend.retrieve_job(self.sim_job.job_id())
        self.assertEqual(self.sim_job.job_id(), retrieved_job.job_id())
        self.assertEqual(self.sim_job.qobj().to_dict(), retrieved_job.qobj().to_dict())
        self.assertEqual(self.sim_job.result().get_counts(), retrieved_job.result().get_counts())

    @requires_device
    def test_retrieve_job_uses_appropriate_backend(self, backend):
        """Test that retrieved jobs come from their appropriate backend."""
        backend_1 = backend
        # Get a second backend.
        backend_2 = None
        provider = backend.provider()
        for my_backend in provider.backends():
            if my_backend.status().operational and my_backend.name() != backend_1.name():
                backend_2 = my_backend
                break
        if not backend_2:
            raise SkipTest('Skipping test that requires multiple backends')

        job_1 = backend_1.run(transpile(ReferenceCircuits.bell(), backend_1), validate_qobj=True)
        job_2 = backend_2.run(transpile(ReferenceCircuits.bell(), backend_2), validate_qobj=True)

        # test a retrieved job's backend is the same as the queried backend
        self.assertEqual(backend_1.retrieve_job(job_1.job_id()).backend().name(),
                         backend_1.name())
        self.assertEqual(backend_2.retrieve_job(job_2.job_id()).backend().name(),
                         backend_2.name())

        # test retrieve requests for jobs that exist on other backends throw errors
        with self.assertWarns(Warning) as context_manager:
            self.assertRaises(IBMQBackendError,
                              backend_1.retrieve_job, job_2.job_id())
        self.assertIn('belongs to', str(context_manager.warning))
        with self.assertWarns(Warning) as context_manager:
            self.assertRaises(IBMQBackendError,
                              backend_2.retrieve_job, job_1.job_id())
        self.assertIn('belongs to', str(context_manager.warning))

        # Cleanup
        for job in [job_1, job_2]:
            cancel_job(job)

    def test_retrieve_job_error(self):
        """Test retrieving an invalid job."""
        self.assertRaises(IBMQBackendError,
                          self.provider.backend.retrieve_job, 'BAD_JOB_ID')

    def test_retrieve_jobs_status(self):
        """Test retrieving jobs filtered by status."""
        status_args = [JobStatus.DONE, 'DONE', [JobStatus.DONE], ['DONE']]
        for arg in status_args:
            with self.subTest(arg=arg):
                backend_jobs = self.sim_backend.jobs(limit=5, skip=5, status=arg,
                                                     start_datetime=self.last_month)
                self.assertTrue(backend_jobs)

                for job in backend_jobs:
                    self.assertTrue(job.status() is JobStatus.DONE,
                                    "Job {} has status {} when it should be DONE"
                                    .format(job.job_id(), job.status()))

    def test_retrieve_multiple_job_statuses(self):
        """Test retrieving jobs filtered by multiple job statuses."""
        statuses_to_filter = [JobStatus.ERROR, JobStatus.CANCELLED]
        status_filters = [
            {'status': [JobStatus.ERROR, JobStatus.CANCELLED],
             'db_filter': None},
            {'status': [JobStatus.CANCELLED],
             'db_filter': {'or': [{'status': {'regexp': '^ERROR'}}]}},
            {'status': [JobStatus.ERROR],
             'db_filter': {'or': [{'status': 'CANCELLED'}]}}
        ]

        job_to_cancel = submit_and_cancel(backend=self.sim_backend)
        job_to_fail = submit_job_bad_shots(backend=self.sim_backend)
        job_to_fail.wait_for_final_state()

        for status_filter in status_filters:
            with self.subTest(status_filter=status_filter):
                job_list = self.sim_backend.jobs(
                    status=status_filter['status'],
                    db_filter=status_filter['db_filter'],
                    start_datetime=self.last_month)
                job_list_ids = [_job.job_id() for _job in job_list]
                if job_to_cancel.status() is JobStatus.CANCELLED:
                    self.assertIn(job_to_cancel.job_id(), job_list_ids)
                self.assertIn(job_to_fail.job_id(), job_list_ids)

                for filtered_job in job_list:
                    self.assertIn(filtered_job._status, statuses_to_filter,
                                  "job {} has status {} but should be one of {}"
                                  .format(filtered_job.job_id(), filtered_job._status,
                                          statuses_to_filter))

    def test_retrieve_active_jobs(self):
        """Test retrieving jobs that are currently unfinished."""
        backend = most_busy_backend(self.provider)
        active_job_statuses = {api_status_to_job_status(status) for status in ApiJobStatus
                               if status not in API_JOB_FINAL_STATES}

        job = backend.run(transpile(ReferenceCircuits.bell(), backend))

        active_jobs = backend.active_jobs()
        if not job.in_final_state():    # Job is still active.
            self.assertIn(job.job_id(), [active_job.job_id() for active_job in active_jobs])

        for active_job in active_jobs:
            self.assertTrue(active_job._status in active_job_statuses,
                            "status for job {} is '{}' but it should be '{}'."
                            .format(active_job.job_id(), active_job._status, active_job_statuses))

        # Cancel job so it doesn't consume more resources.
        cancel_job(job)

    def test_retrieve_jobs_queued(self):
        """Test retrieving jobs that are queued."""
        backend = most_busy_backend(self.provider)
        job = backend.run(transpile(ReferenceCircuits.bell(), backend))

        # Wait for the job to queue, run, or reach a final state.
        leave_states = list(JOB_FINAL_STATES) + [JobStatus.QUEUED, JobStatus.RUNNING]
        while job.status() not in leave_states:
            time.sleep(0.5)

        before_status = job._status
        job_list_queued = backend.jobs(status=JobStatus.QUEUED, limit=5,
                                       start_datetime=self.last_month)
        if before_status is JobStatus.QUEUED and job.status() is JobStatus.QUEUED:
            self.assertIn(job.job_id(), [queued_job.job_id() for queued_job in job_list_queued],
                          "job {} is queued but not retrieved when filtering for queued jobs."
                          .format(job.job_id()))

        for queued_job in job_list_queued:
            self.assertTrue(queued_job._status == JobStatus.QUEUED,
                            "status for job {} is '{}' but it should be {}"
                            .format(queued_job.job_id(), queued_job._status, JobStatus.QUEUED))

        # Cancel job so it doesn't consume more resources.
        cancel_job(job)

    def test_retrieve_jobs_running(self):
        """Test retrieving jobs that are running."""
        job = self.sim_backend.run(self.bell)

        # Wait for the job to run, or reach a final state.
        leave_states = list(JOB_FINAL_STATES) + [JobStatus.RUNNING]
        while job.status() not in leave_states:
            time.sleep(0.5)

        before_status = job._status
        job_list_running = self.sim_backend.jobs(status=JobStatus.RUNNING, limit=5,
                                                 start_datetime=self.last_month)
        if before_status is JobStatus.RUNNING and job.status() is JobStatus.RUNNING:
            self.assertIn(job.job_id(), [rjob.job_id() for rjob in job_list_running])

        for rjob in job_list_running:
            self.assertTrue(rjob._status == JobStatus.RUNNING,
                            "Status for job {} is '{}' but should be RUNNING"
                            .format(rjob.job_id(), rjob._status))

    def test_retrieve_jobs_start_datetime(self):
        """Test retrieving jobs created after a specified datetime."""
        past_month = datetime.now() - timedelta(days=30)
        # Add local tz in order to compare to `creation_date` which is tz aware.
        past_month_tz_aware = past_month.replace(tzinfo=tz.tzlocal())

        job_list = self.provider.backend.jobs(backend_name=self.sim_backend.name(),
                                              limit=2, start_datetime=past_month)
        self.assertTrue(job_list)
        for job in job_list:
            self.assertGreaterEqual(job.creation_date(), past_month_tz_aware,
                                    'job {} creation date {} not within range'
                                    .format(job.job_id(), job.creation_date()))

    def test_retrieve_jobs_end_datetime(self):
        """Test retrieving jobs created before a specified datetime."""
        past_month = datetime.now() - timedelta(days=30)
        # Add local tz in order to compare to `creation_date` which is tz aware.
        past_month_tz_aware = past_month.replace(tzinfo=tz.tzlocal())

        job_list = self.provider.backend.jobs(backend_name=self.sim_backend.name(),
                                              limit=2, end_datetime=past_month)
        self.assertTrue(job_list)
        for job in job_list:
            self.assertLessEqual(job.creation_date(), past_month_tz_aware,
                                 'job {} creation date {} not within range'
                                 .format(job.job_id(), job.creation_date()))

    def test_retrieve_jobs_between_datetimes(self):
        """Test retrieving jobs created between two specified datetimes."""
        date_today = datetime.now()
        past_month = date_today - timedelta(30)
        past_two_month = date_today - timedelta(60)

        # Used for `db_filter`, should not override `start_datetime` and `end_datetime` arguments.
        past_ten_days = date_today - timedelta(10)
        db_filters = [None, {'creationDate': {'gt': past_ten_days}}]

        # Add local tz in order to compare to `creation_date` which is tz aware.
        past_month_tz_aware = past_month.replace(tzinfo=tz.tzlocal())
        past_two_month_tz_aware = past_two_month.replace(tzinfo=tz.tzlocal())

        for db_filter in db_filters:
            with self.subTest(db_filter=db_filter):
                job_list = self.provider.backend.jobs(
                    backend_name=self.sim_backend.name(), limit=2,
                    start_datetime=past_two_month, end_datetime=past_month, db_filter=db_filter)
                self.assertTrue(job_list)
                for job in job_list:
                    self.assertTrue(
                        (past_two_month_tz_aware <= job.creation_date() <= past_month_tz_aware),
                        'job {} creation date {} not within range'.format(
                            job.job_id(), job.creation_date()))

    def test_retrieve_jobs_db_filter(self):
        """Test retrieving jobs using db_filter."""
        # Submit jobs with desired attributes.
        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.measure([0, 1, 2], [0, 1, 2])
        job = self.sim_backend.run(transpile(qc, backend=self.sim_backend))
        job.wait_for_final_state()

        my_filter = {'backend.name': self.sim_backend.name(),
                     'summaryData.summary.qobj_config.n_qubits': 3,
                     'status': 'COMPLETED'}

        job_list = self.provider.backend.jobs(backend_name=self.sim_backend.name(),
                                              limit=2, skip=0, db_filter=my_filter,
                                              start_datetime=self.last_month)
        self.assertTrue(job_list)

        for job in job_list:
            job.refresh()
            self.assertEqual(
                job.summary_data_['summary']['qobj_config']['n_qubits'], 3,
                "Job {} does not have correct data.".format(job.job_id())
            )

    def test_pagination_filter(self):
        """Test db_filter that could conflict with pagination."""
        jobs = self.sim_backend.jobs(limit=25, start_datetime=self.last_month)
        job = jobs[3]
        job_utc = local_to_utc(job.creation_date()).isoformat()

        db_filters = [
            {'id': {'neq': job.job_id()}},
            {'and': [{'id': {'neq': job.job_id()}}]},
            {'creationDate': {'neq': job_utc}},
            {'and': [{'creationDate': {'gt': job_utc}}]}
        ]
        for db_filter in db_filters:
            with self.subTest(filter=db_filter):
                job_list = self.sim_backend.jobs(limit=25, db_filter=db_filter)
                self.assertTrue(job_list)
                self.assertNotIn(job.job_id(), [rjob.job_id() for rjob in job_list],
                                 "Job {} with creation date {} should not be returned".format(
                                     job.job_id(), job_utc))

    def test_retrieve_jobs_order(self):
        """Test retrieving jobs with different orders."""
        job = self.sim_backend.run(self.bell)
        job.wait_for_final_state()
        newest_jobs = self.sim_backend.jobs(
            limit=10, status=JobStatus.DONE, descending=True, start_datetime=self.last_month)
        self.assertIn(job.job_id(), [rjob.job_id() for rjob in newest_jobs])

        oldest_jobs = self.sim_backend.jobs(
            limit=10, status=JobStatus.DONE, descending=False, start_datetime=self.last_month)
        self.assertNotIn(job.job_id(), [rjob.job_id() for rjob in oldest_jobs])

    @skip("Skip until aer issue 1214 is fixed")
    def test_retrieve_failed_job_simulator_partial(self):
        """Test retrieving partial results from a simulator backend."""
        job = submit_job_one_bad_instr(self.sim_backend)
        result = job.result(partial=True)

        self.assertIsInstance(result, Result)
        self.assertTrue(result.results[0].success)
        self.assertFalse(result.results[1].success)

    @slow_test
    def test_pulse_job(self):
        """Test running a pulse job."""
        backends = self.provider.backends(open_pulse=True, operational=True)
        if not backends:
            raise SkipTest('Skipping pulse test since no pulse backend found.')

        backend = least_busy(backends)
        config = backend.configuration()
        defaults = backend.defaults()
        inst_map = defaults.instruction_schedule_map

        # Run 2 experiments - 1 with x pulse and 1 without
        x = inst_map.get('x', 0)
        measure = inst_map.get('measure', range(config.n_qubits)) << x.duration
        ground_sched = measure
        excited_sched = x | measure
        schedules = [ground_sched, excited_sched]

        job = backend.run(schedules, meas_level=1, shots=256)
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        self.assertTrue(job.done(), "Job {} didn't complete successfully.".format(job.job_id()))
        self.assertIsNotNone(job.result(), "Job {} has no result.".format(job.job_id()))

    def test_retrieve_from_retired_backend(self):
        """Test retrieving a job from a retired backend."""
        saved_backends = copy.copy(self.provider._backends)
        try:
            del self.provider._backends[self.sim_backend.name()]
            new_job = self.provider.backend.retrieve_job(self.sim_job.job_id())
            self.assertTrue(isinstance(new_job.backend(), IBMQRetiredBackend))
            self.assertNotEqual(new_job.backend().name(), 'unknown')

            new_job2 = self.provider.backend.jobs(
                db_filter={'id': self.sim_job.job_id()}, start_datetime=self.last_month)[0]
            self.assertTrue(isinstance(new_job2.backend(), IBMQRetiredBackend))
            self.assertNotEqual(new_job2.backend().name(), 'unknown')
        finally:
            self.provider._backends = saved_backends

    def test_refresh_job_result(self):
        """Test re-retrieving job result via refresh."""
        result = self.sim_job.result()

        # Save original cached results.
        cached_result = copy.deepcopy(result.to_dict())
        self.assertTrue(cached_result)

        # Modify cached results.
        result.results[0].header.name = 'modified_result'
        self.assertNotEqual(cached_result, result.to_dict())
        self.assertEqual(result.results[0].header.name, 'modified_result')

        # Re-retrieve result via refresh.
        result = self.sim_job.result(refresh=True)
        self.assertDictEqual(cached_result, result.to_dict())
        self.assertNotEqual(result.results[0].header.name, 'modified_result')

    def test_wait_for_final_state(self):
        """Test waiting for job to reach final state."""

        def final_state_callback(c_job_id, c_status, c_job, **kwargs):
            """Job status query callback function."""
            self.assertEqual(c_job_id, job.job_id())
            self.assertNotIn(c_status, JOB_FINAL_STATES)
            self.assertEqual(c_job.job_id(), job.job_id())
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
                if callback_info['last call time'] and job._status not in JOB_FINAL_STATES:
                    self.assertAlmostEqual(
                        time.time() - callback_info['last call time'], wait_time, delta=0.2)
                callback_info['last call time'] = time.time()

        def job_canceller(job_, exit_event, wait):
            exit_event.wait(wait)
            cancel_job(job_)

        wait_args = [2, None]

        saved_api = self.sim_backend._api_client
        try:
            self.sim_backend._api_client = BaseFakeAccountClient(job_class=CancelableFakeJob)
            for wait_time in wait_args:
                with self.subTest(wait_time=wait_time):
                    # Put callback data in a dictionary to make it mutable.
                    callback_info = {'called': False, 'last call time': 0.0, 'last data': {}}
                    cancel_event = Event()
                    job = self.sim_backend.run(self.bell)
                    # Cancel the job after a while.
                    Thread(target=job_canceller, args=(job, cancel_event, 7), daemon=True).start()
                    try:
                        job.wait_for_final_state(timeout=10, wait=wait_time,
                                                 callback=final_state_callback)
                        self.assertTrue(job.in_final_state())
                        self.assertTrue(callback_info['called'])
                        cancel_event.set()
                    finally:
                        # Ensure all threads ended.
                        for thread in job._executor._threads:
                            thread.join(0.1)
        finally:
            self.sim_backend._api_client = saved_api

    def test_wait_for_final_state_timeout(self):
        """Test waiting for job to reach final state times out."""
        backend = most_busy_backend(self.provider)
        job = backend.run(transpile(ReferenceCircuits.bell(), backend=backend),
                          validate_qobj=True)
        try:
            self.assertRaises(IBMQJobTimeoutError, job.wait_for_final_state, timeout=0.1)
        finally:
            # Ensure all threads ended.
            for thread in job._executor._threads:
                thread.join(0.1)
            cancel_job(job)

    def test_job_submit_partial_fail(self):
        """Test job submit partial fail."""
        job_id = []

        def _side_effect(self, *args, **kwargs):
            # pylint: disable=unused-argument
            job_id.append(self.job_id)
            raise RequestsApiError('Kaboom')

        fail_points = ['put_object_storage', 'callback_upload']

        for fail_method in fail_points:
            with self.subTest(fail_method=fail_method):
                with mock.patch.object(RestJob, fail_method,
                                       side_effect=_side_effect, autospec=True):
                    with self.assertRaises(IBMQBackendApiError):
                        self.sim_backend.run(self.bell)

                self.assertTrue(job_id, "Job ID not saved.")
                job = self.sim_backend.retrieve_job(job_id[0])
                self.assertEqual(job.status(), JobStatus.CANCELLED,
                                 f"Job {job.job_id()} status is {job.status()} and not cancelled!")

    def test_job_circuits(self):
        """Test job circuits."""
        self.assertEqual(str(self.bell), str(self.sim_job.circuits()[0]))

    def test_job_backend_options(self):
        """Test job backend options."""
        run_config = {'shots': 2048, 'memory': True}
        job = self.sim_backend.run(self.bell, **run_config)
        self.assertLessEqual(run_config.items(), job.backend_options().items())

    def test_job_header(self):
        """Test job header."""
