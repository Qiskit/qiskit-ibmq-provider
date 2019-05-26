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

"""IBMQJob Test."""

import os
import time
import unittest
import warnings
from concurrent import futures

import numpy
from scipy.stats import chi2_contingency

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.providers import JobError, JobStatus
from qiskit.providers.ibmq import IBMQ, least_busy
from qiskit.providers.ibmq.exceptions import IBMQBackendError
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob
from qiskit.test import requires_qe_access, slow_test
from qiskit.compiler import assemble, transpile
from ..jobtestcase import JobTestCase


class TestIBMQJob(JobTestCase):
    """Test ibmqjob module."""

    def setUp(self):
        super().setUp()
        self._qc = _bell_circuit()

    @requires_qe_access
    def test_run_simulator(self, qe_token, qe_url):
        """Test running in a simulator."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

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

    @slow_test
    @requires_qe_access
    def test_run_device(self, qe_token, qe_url):
        """Test running in a real device."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = least_busy(IBMQ.backends(simulator=False))

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

    @slow_test
    @requires_qe_access
    def test_run_async_simulator(self, qe_token, qe_url):
        """Test running in a simulator asynchronously."""
        IBMQJob._executor = futures.ThreadPoolExecutor(max_workers=2)

        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

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

    @slow_test
    @requires_qe_access
    def test_run_async_device(self, qe_token, qe_url):
        """Test running in a real device asynchronously."""
        IBMQ.enable_account(qe_token, qe_url)
        backends = IBMQ.backends(simulator=False)
        backend = least_busy(backends)

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
        result_array = [job.result() for job in job_array]

        # Ensure all jobs have finished.
        self.assertTrue(
            all([job.status() is JobStatus.DONE for job in job_array]))
        self.assertTrue(all([result.success for result in result_array]))

        # Ensure job ids are unique.
        job_ids = [job.job_id() for job in job_array]
        self.assertEqual(sorted(job_ids), sorted(list(set(job_ids))))

    @slow_test
    @requires_qe_access
    def test_cancel(self, qe_token, qe_url):
        """Test job cancelation."""
        IBMQ.enable_account(qe_token, qe_url)
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        backend = IBMQ.get_backend(backend_name)

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)
        self.wait_for_initialization(job, timeout=5)
        can_cancel = job.cancel()
        self.assertTrue(can_cancel)
        self.assertTrue(job.status() is JobStatus.CANCELLED)

    @requires_qe_access
    def test_job_id(self, qe_token, qe_url):
        """Test getting a job id."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)
        self.log.info('job_id: %s', job.job_id())
        self.assertTrue(job.job_id() is not None)

    @requires_qe_access
    def test_get_backend_name(self, qe_token, qe_url):
        """Test getting a backend name."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)
        self.assertTrue(job.backend().name() == backend.name())

    @requires_qe_access
    def test_get_jobs_from_backend(self, qe_token, qe_url):
        """Test retrieving jobs from a backend."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = least_busy(IBMQ.backends())

        start_time = time.time()
        job_list = backend.jobs(limit=5, skip=0)
        self.log.info('time to get jobs: %0.3f s', time.time() - start_time)
        self.log.info('found %s jobs on backend %s',
                      len(job_list), backend.name())
        for job in job_list:
            self.log.info('status: %s', job.status())
            self.assertTrue(isinstance(job.job_id(), str))
        self.log.info('time to get job statuses: %0.3f s',
                      time.time() - start_time)

    @requires_qe_access
    def test_retrieve_job(self, qe_token, qe_url):
        """Test retrieving a single job."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        job = backend.run(qobj)

        rjob = backend.retrieve_job(job.job_id())
        self.assertEqual(job.job_id(), rjob.job_id())
        self.assertEqual(job.result().get_counts(), rjob.result().get_counts())
        self.assertEqual(job.qobj().as_dict(), qobj.as_dict())

    @slow_test
    @requires_qe_access
    def test_retrieve_job_uses_appropriate_backend(self, qe_token, qe_url):
        """Test that retrieved jobs come from their appropriate backend."""
        IBMQ.enable_account(qe_token, qe_url)
        simulator_backend = IBMQ.get_backend('ibmq_qasm_simulator')
        backends = IBMQ.backends(simulator=False)
        real_backend = least_busy(backends)

        qobj_sim = assemble(
            transpile(self._qc, backend=simulator_backend), backend=simulator_backend)
        job_sim = simulator_backend.run(qobj_sim)

        qobj_real = assemble(
            transpile(self._qc, backend=real_backend), backend=real_backend)
        job_real = real_backend.run(qobj_real)

        # test a retrieved job's backend is the same as the queried backend
        self.assertEqual(simulator_backend.retrieve_job(job_sim.job_id()).backend().name(),
                         simulator_backend.name())
        self.assertEqual(real_backend.retrieve_job(job_real.job_id()).backend().name(),
                         real_backend.name())

        # test retrieve requests for jobs that exist on other backends throw errors
        with self.assertWarns(Warning) as context_manager:
            self.assertRaises(IBMQBackendError,
                              simulator_backend.retrieve_job, job_real.job_id())
        self.assertIn('belongs to', str(context_manager.warning))
        with self.assertWarns(Warning) as context_manager:
            self.assertRaises(IBMQBackendError,
                              real_backend.retrieve_job, job_sim.job_id())
        self.assertIn('belongs to', str(context_manager.warning))

    @requires_qe_access
    def test_retrieve_job_error(self, qe_token, qe_url):
        """Test retrieving an invalid job."""
        IBMQ.enable_account(qe_token, qe_url)
        backends = IBMQ.backends(simulator=False)
        backend = least_busy(backends)

        self.assertRaises(IBMQBackendError, backend.retrieve_job, 'BAD_JOB_ID')

    @requires_qe_access
    def test_get_jobs_filter_job_status(self, qe_token, qe_url):
        """Test retrieving jobs from a backend filtered by status."""
        IBMQ.enable_account(qe_token, qe_url)
        backends = IBMQ.backends(simulator=False)
        backend = least_busy(backends)

        with warnings.catch_warnings():
            # Disable warnings from pre-qobj jobs.
            warnings.filterwarnings('ignore',
                                    category=DeprecationWarning,
                                    module='qiskit.providers.ibmq.ibmqbackend')
            job_list = backend.jobs(limit=5, skip=0, status=JobStatus.DONE)

        for job in job_list:
            self.assertTrue(job.status() is JobStatus.DONE)

    @requires_qe_access
    def test_get_jobs_filter_counts(self, qe_token, qe_url):
        """Test retrieving jobs from a backend filtered by counts."""
        # TODO: consider generalizing backend name
        # TODO: this tests depends on the previous executions of the user
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

        my_filter = {'backend.name': 'ibmq_qasm_simulator',
                     'shots': 1024,
                     'qasms.result.data.counts.00': {'lt': 500}}
        self.log.info('searching for at most 5 jobs with 1024 shots, a count '
                      'for "00" of < 500, on the ibmq_qasm_simulator backend')

        with warnings.catch_warnings():
            # Disable warnings from pre-qobj jobs.
            warnings.filterwarnings('ignore',
                                    category=DeprecationWarning,
                                    module='qiskit.providers.ibmq.ibmqbackend')
            job_list = backend.jobs(limit=5, skip=0, db_filter=my_filter)

        for i, job in enumerate(job_list):
            self.log.info('match #%d', i)
            result = job.result()
            self.assertTrue(any(cresult.data.counts.to_dict()['0x0'] < 500
                                for cresult in result.results))

    @requires_qe_access
    def test_get_jobs_filter_date(self, qe_token, qe_url):
        """Test retrieving jobs from a backend filtered by date."""
        IBMQ.enable_account(qe_token, qe_url)
        backends = IBMQ.backends(simulator=False)
        backend = least_busy(backends)

        my_filter = {'creationDate': {'lt': '2017-01-01T00:00:00.00'}}
        job_list = backend.jobs(limit=5, db_filter=my_filter)
        self.log.info('found %s matching jobs', len(job_list))
        for i, job in enumerate(job_list):
            self.log.info('match #%d: %s', i, job.creation_date)
            self.assertTrue(job.creation_date < '2017-01-01T00:00:00.00')

    @requires_qe_access
    def test_double_submit_fails(self, qe_token, qe_url):
        """Test submitting a job twice."""
        IBMQ.enable_account(qe_token, qe_url)
        backend = IBMQ.get_backend('ibmq_qasm_simulator')

        qobj = assemble(transpile(self._qc, backend=backend), backend=backend)
        # backend.run() will automatically call job.submit()
        job = backend.run(qobj)
        with self.assertRaises(JobError):
            job.submit()


@unittest.skip('Temporarily disabled, see #1162')
class TestQobjBasedIBMQJob(JobTestCase):
    """Test jobs supporting Qobj."""

    def setUp(self):
        super().setUp()
        self._testing_device = os.getenv('IBMQ_QOBJ_DEVICE', None)
        self._qe_token = os.getenv('IBMQ_TOKEN', None)
        self._qe_url = os.getenv('IBMQ_QOBJ_URL')
        if not self._testing_device or not self._qe_token or not self._qe_url:
            self.skipTest('No credentials or testing device available for '
                          'testing Qobj capabilities.')

        IBMQ.enable_account(self._qe_token, self._qe_url)
        self._backend = IBMQ.get_backend(self._testing_device)

        self._qc = _bell_circuit()

    def test_qobj_enabled_job(self):
        """Job should be an instance of IBMQJob."""
        qobj = assemble(
            transpile(self._qc, backend=self._backend), backend=self._backend)
        job = self._backend.run(qobj)
        self.assertIsInstance(job, IBMQJob)

    def test_qobj_enabled_result(self):
        """Jobs can be retrieved."""
        qobj = assemble(
            transpile(self._qc, backend=self._backend), backend=self._backend)
        job = self._backend.run(qobj)
        try:
            job.result()
        except JobError as err:
            self.fail(err)


def _bell_circuit():
    qr = QuantumRegister(2, 'q')
    cr = ClassicalRegister(2, 'c')
    qc = QuantumCircuit(qr, cr)
    qc.h(qr[0])
    qc.cx(qr[0], qr[1])
    qc.measure(qr, cr)
    return qc
