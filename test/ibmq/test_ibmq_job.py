# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
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
from concurrent import futures
from datetime import datetime, timedelta
from unittest import SkipTest

import numpy
from scipy.stats import chi2_contingency

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.providers import JobStatus
from qiskit.providers.ibmq import least_busy
from qiskit.providers.ibmq.ibmqbackend import IBMQRetiredBackend
from qiskit.providers.ibmq.exceptions import IBMQBackendError
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob
from qiskit.providers.ibmq.job.exceptions import IBMQJobInvalidStateError, JobError
from qiskit.test import slow_test
from qiskit.compiler import assemble, transpile
from qiskit.result import Result

from ..jobtestcase import JobTestCase
from ..decorators import requires_provider, slow_test_on_device, requires_device


class TestIBMQJob(JobTestCase):
    """Test ibmqjob module."""

    def setUp(self):
        super().setUp()
        self._qc = _bell_circuit()

    @requires_provider
    def test_run_simulator(self, provider):
        """Test running in a simulator."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qr = QuantumRegister(2, 'q')
        cr = ClassicalRegister(2, 'c')
        qc = QuantumCircuit(qr, cr, name='hadamard')
        qc.h(qr)
        qc.measure(qr, cr)
        qobj = assemble(transpile([self._qc, qc], backend=backend), backend=backend)
        shots = qobj.config.shots
        job = backend.run(qobj)
        result = job.result()
        counts_qx1 = result.get_counts(0)
        counts_qx2 = result.get_counts(1)
        counts_ex1 = {'00': shots / 2, '11': shots / 2}
        counts_ex2 = {'00': shots / 4, '11': shots / 4, '10': shots / 4, '01': shots / 4}
        states1 = counts_qx1.keys() | counts_ex1.keys()
        states2 = counts_qx2.keys() | counts_ex2.keys()
        # contingency table
        ctable1 = numpy.array([[counts_qx1.get(key, 0) for key in states1],
                               [counts_ex1.get(key, 0) for key in states1]])
        ctable2 = numpy.array([[counts_qx2.get(key, 0) for key in states2],
                               [counts_ex2.get(key, 0) for key in states2]])
        self.log.info('states1: %s', str(states1))
        self.log.info('states2: %s', str(states2))
        self.log.info('ctable1: %s', str(ctable1))
        self.log.info('ctable2: %s', str(ctable2))
        contingency1 = chi2_contingency(ctable1)
        contingency2 = chi2_contingency(ctable2)
        self.log.info('chi2_contingency1: %s', str(contingency1))
        self.log.info('chi2_contingency2: %s', str(contingency2))
        self.assertGreater(contingency1[1], 0.01)
        self.assertGreater(contingency2[1], 0.01)

    @slow_test_on_device
    def test_run_device(self, provider, backend):   # pylint: disable=unused-argument
        """Test running in a real device."""
        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        shots = qobj.config.shots
        job = backend.run(qobj)
        while not job.status() is JobStatus.DONE:
            time.sleep(4)

        result = job.result()
        counts_qx = result.get_counts(0)
        counts_ex = {'00': shots / 2, '11': shots / 2}
        self.assertDictAlmostEqual(counts_qx, counts_ex, shots * 0.1)

        # Test fetching the job properties, as this is a real backend and is
        # guaranteed to have them.
        _ = job.properties()

    @requires_provider
    def test_run_async_simulator(self, provider):
        """Test running in a simulator asynchronously."""
        IBMQJob._executor = futures.ThreadPoolExecutor(max_workers=2)

        backend = provider.get_backend('ibmq_qasm_simulator')

        self.log.info('submitting to backend %s', backend.name())
        num_qubits = 16
        qr = QuantumRegister(num_qubits, 'qr')
        cr = ClassicalRegister(num_qubits, 'cr')
        qc = QuantumCircuit(qr, cr)
        for i in range(num_qubits - 1):
            qc.cx(qr[i], qr[i + 1])
        qc.measure(qr, cr)
        qobj = assemble(transpile([qc] * 10, backend=backend), backend=backend)
        num_jobs = 5
        job_array = [backend.run(qobj) for _ in range(num_jobs)]
        found_async_jobs = False
        timeout = 30
        start_time = time.time()
        while not found_async_jobs:
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
            if time.time() - start_time > timeout:
                raise TimeoutError('failed to see multiple running jobs after '
                                   '{0} s'.format(timeout))
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

    @slow_test_on_device
    def test_run_async_device(self, provider, backend):  # pylint: disable=unused-argument
        """Test running in a real device asynchronously."""
        self.log.info('submitting to backend %s', backend.name())
        num_qubits = 5
        qr = QuantumRegister(num_qubits, 'qr')
        cr = ClassicalRegister(num_qubits, 'cr')
        qc = QuantumCircuit(qr, cr)
        for i in range(num_qubits - 1):
            qc.cx(qr[i], qr[i + 1])
        qc.measure(qr, cr)
        qobj = assemble(transpile(qc, backend=backend), backend=backend)
        num_jobs = 3
        job_array = [backend.run(qobj) for _ in range(num_jobs)]
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
        result_array = [job.result(timeout=180) for job in job_array]

        # Ensure all jobs have finished.
        self.assertTrue(
            all([job.status() is JobStatus.DONE for job in job_array]))
        self.assertTrue(all([result.success for result in result_array]))

        # Ensure job ids are unique.
        job_ids = [job.job_id() for job in job_array]
        self.assertEqual(sorted(job_ids), sorted(list(set(job_ids))))

    @requires_provider
    def test_cancel(self, provider):
        """Test job cancellation."""
        # Find the most busy backend
        backend = max([b for b in provider.backends() if b.status().operational],
                      key=lambda b: b.status().pending_jobs)

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)
        can_cancel = job.cancel()
        self.assertTrue(can_cancel)
        self.assertTrue(job.status() is JobStatus.CANCELLED)

    @requires_provider
    def test_retrieve_jobs(self, provider):
        """Test retrieving jobs."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        job_list = provider.backends.jobs(backend_name=backend.name(), limit=5, skip=0)
        for job in job_list:
            self.assertTrue(isinstance(job.job_id(), str))

    @requires_provider
    def test_retrieve_job(self, provider):
        """Test retrieving a single job."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)

        retrieved_job = provider.backends.retrieve_job(job.job_id())
        self.assertEqual(job.job_id(), retrieved_job.job_id())
        self.assertEqual(job.result().get_counts(), retrieved_job.result().get_counts())
        self.assertEqual(job.qobj().to_dict(), qobj.to_dict())

    @requires_device
    @requires_provider
    def test_retrieve_job_uses_appropriate_backend(self, backend, provider):
        """Test that retrieved jobs come from their appropriate backend."""
        backend_1 = backend
        # Get a second backend.
        backend_2 = None
        for backend_2 in provider.backends():
            if backend_2.status().operational and backend_2.name() != backend_1.name():
                break
        if not backend_2:
            raise SkipTest('Skipping test that requires multiple backends')

        qobj_1 = assemble(
            transpile(self._qc, backend=backend_1), backend=backend_1)
        job_1 = backend_1.run(qobj_1)

        qobj_2 = assemble(
            transpile(self._qc, backend=backend_2), backend=backend_2)
        job_2 = backend_2.run(qobj_2)

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
            try:
                job.cancel()
            except JobError:
                pass

    @requires_provider
    def test_retrieve_job_error(self, provider):
        """Test retrieving an invalid job."""
        self.assertRaises(IBMQBackendError, provider.backends.retrieve_job, 'BAD_JOB_ID')

    @requires_provider
    def test_retrieve_jobs_status(self, provider):
        """Test retrieving jobs filtered by status."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        job_list = provider.backends.jobs(backend_name=backend.name(),
                                          limit=5, skip=0, status=JobStatus.DONE)

        self.assertTrue(job_list)
        for job in job_list:
            self.assertTrue(job.status() is JobStatus.DONE)

    @requires_provider
    def test_retrieve_jobs_start_datetime(self, provider):
        """Test retrieving jobs created after a specified datetime."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        past_month = datetime.now() - timedelta(days=30)
        past_month_str = past_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        job_list = provider.backends.jobs(backend_name=backend.name(),
                                          limit=5, skip=0, start_datetime=past_month)
        self.assertTrue(job_list)
        for i, job in enumerate(job_list):
            self.assertTrue(job.creation_date() >= past_month_str,
                            '{}) job creation_date {} is not '
                            'greater than or equal to past month: {}'
                            .format(i, job.creation_date(), past_month_str))

    @requires_provider
    def test_retrieve_jobs_end_datetime(self, provider):
        """Test retrieving jobs created before a specified datetime."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        past_month = datetime.now() - timedelta(days=30)
        past_month_str = past_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        job_list = provider.backends.jobs(backend_name=backend.name(),
                                          limit=5, skip=0, end_datetime=past_month)
        self.assertTrue(job_list)
        for i, job in enumerate(job_list):
            self.assertTrue(job.creation_date() <= past_month_str,
                            '{}) job creation_date {} is not '
                            'less than or equal to past month: {}'
                            .format(i, job.creation_date(), past_month_str))

    @requires_provider
    def test_retrieve_jobs_between_datetimes(self, provider):
        """Test retrieving jobs created between two specified datetimes."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        date_today = datetime.now()

        past_month = date_today - timedelta(30)
        past_month_str = past_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        past_two_month = date_today - timedelta(60)
        past_two_month_str = past_two_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        job_list = provider.backends.jobs(backend_name=backend.name(), limit=5, skip=0,
                                          start_datetime=past_two_month, end_datetime=past_month)
        self.assertTrue(job_list)
        for i, job in enumerate(job_list):
            self.assertTrue((past_two_month_str <= job.creation_date() <= past_month_str),
                            '{}) job creation date {} is not '
                            'between past two month {} and past month {}'
                            .format(i, past_two_month_str, job.creation_date(), past_month_str))

    @requires_provider
    def test_retrieve_jobs_between_datetimes_not_overriden(self, provider):
        """Test retrieving jobs created between two specified datetimes
        and ensure `db_filter` does not override datetime arguments."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        date_today = datetime.now()

        past_two_month = date_today - timedelta(30)
        past_two_month_str = past_two_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        past_three_month = date_today - timedelta(60)
        past_three_month_str = past_three_month.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        # Used for `db_filter`, should not override `start_datetime` and `end_datetime` arguments.
        past_ten_days = date_today - timedelta(10)

        job_list = provider.backends.jobs(backend_name=backend.name(), limit=5, skip=0,
                                          start_datetime=past_three_month,
                                          end_datetime=past_two_month,
                                          db_filter={'creationDate': {'gt': past_ten_days}})
        self.assertTrue(job_list)
        for i, job in enumerate(job_list):
            self.assertTrue((past_three_month_str <= job.creation_date() <= past_two_month_str),
                            '{}) job creation date {} is not '
                            'between past three month {} and past two month {}'
                            .format(i, past_three_month_str,
                                    job.creation_date(), past_two_month_str))

    @requires_provider
    def test_retrieve_jobs_db_filter(self, provider):
        """Test retrieving jobs using db_filter."""
        # TODO: consider generalizing backend name
        backend = provider.get_backend('ibmq_qasm_simulator')

        # Submit jobs with desired attributes.
        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.measure([0, 1, 2], [0, 1, 2])
        qobj = assemble(transpile(qc, backend=backend), backend=backend)
        for _ in range(2):
            backend.run(qobj).result()

        my_filter = {'backend.name': backend.name(),
                     'summaryData.summary.qobj_config.n_qubits': 3,
                     'status': 'COMPLETED'}

        job_list = provider.backends.jobs(backend_name=backend.name(),
                                          limit=2, skip=0, db_filter=my_filter)
        self.assertTrue(job_list)

        for job in job_list:
            job.refresh()
            self.assertEqual(
                job.summary_data['summary']['qobj_config']['n_qubits'], 3,
                "Job {} does not have correct data.".format(job.job_id())
            )

    @requires_provider
    def test_retrieve_jobs_filter_date(self, provider):
        """Test retrieving jobs filtered by date."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        date_today = datetime.now()
        date_today_str = date_today.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        my_filter = {'creationDate': {'lt': date_today.isoformat()}}
        job_list = provider.backends.jobs(backend_name=backend.name(),
                                          limit=5, db_filter=my_filter)

        self.assertTrue(job_list)
        self.log.info('found %s matching jobs', len(job_list))
        for i, job in enumerate(job_list):
            self.log.info('match #%d: %s', i, job.creation_date())
            self.assertTrue(job.creation_date() < date_today_str,
                            '{}) job.creation_date: {}, date_today: {}'
                            .format(i, job.creation_date(), date_today_str))

    @requires_provider
    def test_double_submit_fails(self, provider):
        """Test submitting a job twice."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        # backend.run() will automatically call job.submit()
        job = backend.run(qobj)
        with self.assertRaises(IBMQJobInvalidStateError):
            job.submit()

    @requires_provider
    def test_retrieve_failed_job_simulator_partial(self, provider):
        """Test retrieving partial results from a simulator backend."""
        backend = provider.get_backend('ibmq_qasm_simulator')

        qc_new = transpile(self._qc, backend)
        qobj = assemble([qc_new, qc_new], backend=backend)
        qobj.experiments[1].instructions[1].name = 'bad_instruction'

        job = backend.run(qobj)
        result = job.result(partial=True)

        self.assertIsInstance(result, Result)
        self.assertTrue(result.results[0].success)
        self.assertFalse(result.results[1].success)

    @slow_test
    @requires_provider
    def test_pulse_job(self, provider):
        """Test running a pulse job."""
        backends = provider.backends(open_pulse=True, operational=True)
        if not backends:
            raise SkipTest('Skipping pulse test since no pulse backend found.')

        backend = least_busy(backends)
        config = backend.configuration()
        defaults = backend.defaults()
        inst_map = defaults.circuit_instruction_map

        # Run 2 experiments - 1 with x pulse and 1 without
        x = inst_map.get('x', 0)
        measure = inst_map.get('measure', range(config.n_qubits)) << x.duration
        ground_sched = measure
        excited_sched = x | measure
        schedules = [ground_sched, excited_sched]

        qobj = assemble(schedules, backend, meas_level=1, shots=256)
        job = backend.run(qobj)
        _ = job.result()

    @requires_provider
    def test_retrieve_from_retired_backend(self, provider):
        """Test retrieving a job from a retired backend."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)

        del provider._backends['ibmq_qasm_simulator']
        new_job = provider.backends.retrieve_job(job.job_id())
        self.assertTrue(isinstance(new_job.backend(), IBMQRetiredBackend))
        self.assertNotEqual(new_job.backend().name(), 'unknown')

        new_job2 = provider.backends.jobs(db_filter={'id': job.job_id()})[0]
        self.assertTrue(isinstance(new_job2.backend(), IBMQRetiredBackend))
        self.assertNotEqual(new_job2.backend().name(), 'unknown')

    @requires_provider
    def test_refresh_job_result(self, provider):
        """Test re-retrieving job result via refresh."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)
        result = job.result()

        # Save original cached results.
        cached_result = copy.deepcopy(result)
        self.assertTrue(cached_result)

        # Modify cached results.
        result.results[0].header.name = 'modified_result'
        self.assertNotEqual(cached_result, result)
        self.assertEqual(result.results[0].header.name, 'modified_result')

        # Re-retrieve result via refresh.
        result = job.result(refresh=True)
        self.assertEqual(cached_result, result)
        self.assertNotEqual(result.results[0].header.name, 'modified_result')


def _bell_circuit():
    qr = QuantumRegister(2, 'q')
    cr = ClassicalRegister(2, 'c')
    qc = QuantumCircuit(qr, cr)
    qc.h(qr[0])
    qc.cx(qr[0], qr[1])
    qc.measure(qr, cr)
    return qc
