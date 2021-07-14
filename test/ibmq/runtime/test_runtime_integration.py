# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for runtime service."""

import unittest
import os
import uuid
import time
import random
from contextlib import suppress

from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.runtime.constants import API_TO_JOB_ERROR_MESSAGE
from qiskit.providers.ibmq.exceptions import IBMQNotAuthorizedError
from qiskit.providers.ibmq.runtime.runtime_program import RuntimeProgram
from qiskit.providers.ibmq.runtime.exceptions import (RuntimeDuplicateProgramError,
                                                      RuntimeProgramNotFound,
                                                      RuntimeJobFailureError,
                                                      RuntimeInvalidStateError,
                                                      RuntimeJobNotFound)

from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_runtime_device
from ...proxy_server import MockProxyServer, use_proxies
from .utils import SerializableClass, SerializableClassDecoder, get_complex_types


@unittest.skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
class TestRuntimeIntegration(IBMQTestCase):
    """Integration tests for runtime modules."""

    RUNTIME_PROGRAM = """
import random
import time
import warnings

from qiskit import transpile
from qiskit.circuit.random import random_circuit

def prepare_circuits(backend):
    circuit = random_circuit(num_qubits=5, depth=4, measure=True,
                             seed=random.randint(0, 1000))
    return transpile(circuit, backend)

def main(backend, user_messenger, **kwargs):
    iterations = kwargs['iterations']
    sleep_per_iteration = kwargs.pop('sleep_per_iteration', 0)
    interim_results = kwargs.pop('interim_results', {})
    final_result = kwargs.pop("final_result", {})
    for it in range(iterations):
        time.sleep(sleep_per_iteration)
        qc = prepare_circuits(backend)
        user_messenger.publish({"iteration": it, "interim_results": interim_results})
        backend.run(qc).result()

    user_messenger.publish(final_result, final=True)
    print("this is a stdout message")
    warnings.warn("this is a stderr message")
    """

    RUNTIME_PROGRAM_METADATA = {
        "max_execution_time": 600,
        "description": "Qiskit test program"
    }
    PROGRAM_PREFIX = 'qiskit-test'

    @classmethod
    @requires_runtime_device
    def setUpClass(cls, backend):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.backend = backend
        cls.poll_time = 1 if backend.configuration().simulator else 5
        cls.provider = backend.provider()
        cls.program_id = cls.PROGRAM_PREFIX
        try:
            cls.program_id = cls.provider.runtime.upload_program(
                name=cls.PROGRAM_PREFIX,
                data=cls.RUNTIME_PROGRAM.encode(),
                metadata=cls.RUNTIME_PROGRAM_METADATA)
        except RuntimeDuplicateProgramError:
            pass
        except IBMQNotAuthorizedError:
            raise unittest.SkipTest("No upload access.")

    @classmethod
    def tearDownClass(cls) -> None:
        """Class level teardown."""
        super().tearDownClass()
        with suppress(Exception):
            cls.provider.runtime.delete_program(cls.program_id)

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        self.to_delete = []
        self.to_cancel = []
        self.proxy_process = None

    def tearDown(self) -> None:
        """Test level teardown."""
        super().tearDown()
        # Delete programs
        for prog in self.to_delete:
            with suppress(Exception):
                self.provider.runtime.delete_program(prog)

        # Cancel and delete jobs.
        for job in self.to_cancel:
            with suppress(Exception):
                job.cancel()
            with suppress(Exception):
                self.provider.runtime.delete_job(job.job_id())

    def test_runtime_service(self):
        """Test getting runtime service."""
        self.assertTrue(self.provider.service('runtime'))

    def test_list_programs(self):
        """Test listing programs."""
        programs = self.provider.runtime.programs()
        self.assertTrue(programs)
        found = False
        for prog in programs:
            self._validate_program(prog)
            if prog.program_id == self.program_id:
                found = True
        self.assertTrue(found, f"Program {self.program_id} not found!")

    def test_list_program(self):
        """Test listing a single program."""
        program = self.provider.runtime.program(self.program_id)
        self.assertEqual(self.program_id, program.program_id)
        self._validate_program(program)

    def test_upload_program(self):
        """Test uploading a program."""
        max_execution_time = 3000
        program_id = self._upload_program(max_execution_time=max_execution_time)
        self.assertTrue(program_id)
        program = self.provider.runtime.program(program_id)
        self.assertTrue(program)
        self.assertEqual(max_execution_time, program.max_execution_time)

    def test_set_visibility(self):
        """Test setting the visibility of a program."""
        program_id = self._upload_program()
        # Get the initial visibility
        prog: RuntimeProgram = self.provider.runtime.program(program_id)
        start_vis = prog.is_public
        # Flip the original value
        self.provider.runtime.set_program_visibility(program_id, not start_vis)
        # Get the new visibility
        prog: RuntimeProgram = self.provider.runtime.program(program_id, refresh=True)
        end_vis = prog.is_public
        # Verify changed
        self.assertNotEqual(start_vis, end_vis)

    def test_upload_program_conflict(self):
        """Test uploading a program with conflicting name."""
        name = self._get_program_name()
        self._upload_program(name=name)
        with self.assertRaises(RuntimeDuplicateProgramError):
            self._upload_program(name=name)

    def test_delete_program(self):
        """Test deleting program."""
        program_id = self._upload_program()
        self.provider.runtime.delete_program(program_id)
        with self.assertRaises(RuntimeProgramNotFound):
            self.provider.runtime.program(program_id, refresh=True)

    def test_double_delete_program(self):
        """Test deleting a deleted program."""
        program_id = self._upload_program()
        self.provider.runtime.delete_program(program_id)
        with self.assertRaises(RuntimeProgramNotFound):
            self.provider.runtime.delete_program(program_id)

    def test_run_program(self):
        """Test running a program."""
        job = self._run_program(final_result="foo")
        result = job.result()
        self.assertEqual(JobStatus.DONE, job.status())
        self.assertEqual("foo", result)

    def test_run_program_failed(self):
        """Test a failed program execution."""
        options = {'backend_name': self.backend.name()}
        job = self.provider.runtime.run(program_id=self.program_id, inputs={}, options=options)
        self.log.info("Runtime job %s submitted.", job.job_id())

        job.wait_for_final_state()
        job_result_raw = self.provider.runtime._api_client.job_results(job.job_id())
        self.assertEqual(JobStatus.ERROR, job.status())
        self.assertIn(API_TO_JOB_ERROR_MESSAGE['FAILED'].format(
            job.job_id(), job_result_raw), job.error_message())
        with self.assertRaises(RuntimeJobFailureError) as err_cm:
            job.result()
        self.assertIn('KeyError', str(err_cm.exception))

    def test_run_program_failed_ran_too_long(self):
        """Test a program that failed since it ran longer than maxiumum execution time."""
        max_execution_time = 60
        inputs = {
            'iterations': 1,
            'sleep_per_iteration': 60
        }
        program_id = self._upload_program(max_execution_time=max_execution_time)
        options = {'backend_name': self.backend.name()}
        job = self.provider.runtime.run(program_id=program_id, inputs=inputs, options=options)
        self.log.info("Runtime job %s submitted.", job.job_id())

        job.wait_for_final_state()
        job_result_raw = self.provider.runtime._api_client.job_results(job.job_id())
        self.assertEqual(JobStatus.ERROR, job.status())
        self.assertIn(API_TO_JOB_ERROR_MESSAGE['CANCELLED - RAN TOO LONG'].format(
            job.job_id(), job_result_raw), job.error_message())
        with self.assertRaises(RuntimeJobFailureError):
            job.result()

    def test_retrieve_job_queued(self):
        """Test retrieving a queued job."""
        _ = self._run_program(iterations=10)
        job = self._run_program(iterations=2)
        self._wait_for_status(job, JobStatus.QUEUED)
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(job.job_id(), rjob.job_id())
        self.assertEqual(self.program_id, rjob.program_id)

    def test_retrieve_job_running(self):
        """Test retrieving a running job."""
        job = self._run_program(iterations=10)
        self._wait_for_status(job, JobStatus.RUNNING)
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(job.job_id(), rjob.job_id())
        self.assertEqual(self.program_id, job.program_id)

    def test_retrieve_job_done(self):
        """Test retrieving a finished job."""
        job = self._run_program()
        job.wait_for_final_state()
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(job.job_id(), rjob.job_id())
        self.assertEqual(self.program_id, job.program_id)

    def test_retrieve_all_jobs(self):
        """Test retrieving all jobs."""
        job = self._run_program()
        rjobs = self.provider.runtime.jobs()
        found = False
        for rjob in rjobs:
            if rjob.job_id() == job.job_id():
                self.assertEqual(job.program_id, rjob.program_id)
                self.assertEqual(job.inputs, rjob.inputs)
                found = True
                break
        self.assertTrue(found, f"Job {job.job_id()} not returned.")

    def test_retrieve_jobs_limit(self):
        """Test retrieving jobs with limit."""
        jobs = []
        for _ in range(3):
            jobs.append(self._run_program())

        rjobs = self.provider.runtime.jobs(limit=2)
        self.assertEqual(len(rjobs), 2)
        job_ids = {job.job_id() for job in jobs}
        rjob_ids = {rjob.job_id() for rjob in rjobs}
        self.assertTrue(rjob_ids.issubset(job_ids))

    def test_retrieve_pending_jobs(self):
        """Test retrieving pending jobs (QUEUED, RUNNING)."""
        job = self._run_program(iterations=10)
        self._wait_for_status(job, JobStatus.RUNNING)
        rjobs = self.provider.runtime.jobs(pending=True)
        found = False
        for rjob in rjobs:
            if rjob.job_id() == job.job_id():
                self.assertEqual(job.program_id, rjob.program_id)
                self.assertEqual(job.inputs, rjob.inputs)
                found = True
                break
        self.assertTrue(found, f"Pending job {job.job_id()} not retrieved.")

    def test_retrieve_returned_jobs(self):
        """Test retrieving returned jobs (COMPLETED, FAILED, CANCELLED)."""
        job = self._run_program()
        job.wait_for_final_state()
        rjobs = self.provider.runtime.jobs(pending=False)
        found = False
        for rjob in rjobs:
            if rjob.job_id() == job.job_id():
                self.assertEqual(job.program_id, rjob.program_id)
                self.assertEqual(job.inputs, rjob.inputs)
                found = True
                break
        self.assertTrue(found, f"Returned job {job.job_id()} not retrieved.")

    def test_cancel_job_queued(self):
        """Test canceling a queued job."""
        _ = self._run_program(iterations=10)
        job = self._run_program(iterations=2)
        self._wait_for_status(job, JobStatus.QUEUED)
        job.cancel()
        self.assertEqual(job.status(), JobStatus.CANCELLED)
        time.sleep(10)  # Wait a bit for DB to update.
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(rjob.status(), JobStatus.CANCELLED)

    def test_cancel_job_running(self):
        """Test canceling a running job."""
        job = self._run_program(iterations=3)
        self._wait_for_status(job, JobStatus.RUNNING)
        job.cancel()
        self.assertEqual(job.status(), JobStatus.CANCELLED)
        time.sleep(10)  # Wait a bit for DB to update.
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(rjob.status(), JobStatus.CANCELLED)

    def test_cancel_job_done(self):
        """Test canceling a finished job."""
        job = self._run_program()
        job.wait_for_final_state()
        with self.assertRaises(RuntimeInvalidStateError):
            job.cancel()

    def test_delete_job(self):
        """Test deleting a job."""
        sub_tests = [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.DONE]
        for status in sub_tests:
            with self.subTest(status=status):
                if status == JobStatus.QUEUED:
                    _ = self._run_program(iterations=10)

                job = self._run_program(iterations=2)
                self._wait_for_status(job, status)
                self.provider.runtime.delete_job(job.job_id())
                with self.assertRaises(RuntimeJobNotFound):
                    self.provider.runtime.job(job.job_id())

    def test_interim_result_callback(self):
        """Test interim result callback."""
        def result_callback(job_id, interim_result):
            nonlocal final_it
            final_it = interim_result['iteration']
            nonlocal callback_err
            if job_id != job.job_id():
                callback_err.append(f"Unexpected job ID: {job_id}")
            if interim_result['interim_results'] != int_res:
                callback_err.append(f"Unexpected interim result: {interim_result}")

        int_res = "foo"
        final_it = 0
        callback_err = []
        iterations = 3
        job = self._run_program(iterations=iterations, interim_results=int_res,
                                callback=result_callback)
        job.wait_for_final_state()
        self.assertEqual(iterations-1, final_it)
        self.assertFalse(callback_err)
        self.assertIsNotNone(job._ws_client._server_close_code)

    def test_stream_results(self):
        """Test stream_results method."""
        def result_callback(job_id, interim_result):
            nonlocal final_it
            final_it = interim_result['iteration']
            nonlocal callback_err
            if job_id != job.job_id():
                callback_err.append(f"Unexpected job ID: {job_id}")
            if interim_result['interim_results'] != int_res:
                callback_err.append(f"Unexpected interim result: {interim_result}")

        int_res = "bar"
        final_it = 0
        callback_err = []
        iterations = 3
        job = self._run_program(iterations=iterations, interim_results=int_res)

        self._wait_for_status(job, JobStatus.RUNNING)
        job.stream_results(result_callback)
        job.wait_for_final_state()
        self.assertEqual(iterations-1, final_it)
        self.assertFalse(callback_err)
        self.assertIsNotNone(job._ws_client._server_close_code)

    def test_stream_results_done(self):
        """Test streaming interim results after job is done."""
        def result_callback(job_id, interim_result):
            # pylint: disable=unused-argument
            nonlocal called_back
            called_back = True

        called_back = False
        job = self._run_program(interim_results="foobar")
        job.wait_for_final_state()
        job._status = JobStatus.RUNNING  # Allow stream_results()
        job.stream_results(result_callback)
        time.sleep(2)
        self.assertFalse(called_back)
        self.assertIsNotNone(job._ws_client._server_close_code)

    def test_callback_error(self):
        """Test error in callback method."""
        def result_callback(job_id, interim_result):
            # pylint: disable=unused-argument
            if interim_result['iteration'] == 0:
                raise ValueError("Kaboom!")
            nonlocal final_it
            final_it = interim_result['iteration']

        final_it = 0
        iterations = 3
        with self.assertLogs('qiskit.providers.ibmq.runtime', level='WARNING') as err_cm:
            job = self._run_program(iterations=iterations, interim_results="foo",
                                    callback=result_callback)
            job.wait_for_final_state()

        self.assertIn("Kaboom", ', '.join(err_cm.output))
        self.assertEqual(iterations-1, final_it)
        self.assertIsNotNone(job._ws_client._server_close_code)

    def test_callback_cancel_job(self):
        """Test canceling a running job while streaming results."""
        def result_callback(job_id, interim_result):
            # pylint: disable=unused-argument
            nonlocal final_it
            final_it = interim_result['iteration']

        final_it = 0
        iterations = 3
        sub_tests = [JobStatus.QUEUED, JobStatus.RUNNING]

        for status in sub_tests:
            with self.subTest(status=status):
                if status == JobStatus.QUEUED:
                    _ = self._run_program(iterations=10)

                job = self._run_program(iterations=iterations, interim_results="foo",
                                        callback=result_callback)
                self._wait_for_status(job, status)
                job.cancel()
                time.sleep(3)  # Wait for cleanup
                self.assertIsNotNone(job._ws_client._server_close_code)
                self.assertLess(final_it, iterations)

    def test_final_result(self):
        """Test getting final result."""
        final_result = get_complex_types()
        job = self._run_program(final_result=final_result)
        result = job.result(decoder=SerializableClassDecoder)
        self.assertEqual(final_result, result)

        rresults = self.provider.runtime.job(job.job_id()).result(decoder=SerializableClassDecoder)
        self.assertEqual(final_result, rresults)

    def test_job_status(self):
        """Test job status."""
        job = self._run_program(iterations=1)
        time.sleep(random.randint(1, 5))
        self.assertTrue(job.status())

    def test_job_inputs(self):
        """Test job inputs."""
        interim_results = get_complex_types()
        inputs = {'iterations': 1,
                  'interim_results': interim_results}
        options = {'backend_name': self.backend.name()}
        job = self.provider.runtime.run(program_id=self.program_id, inputs=inputs,
                                        options=options)
        self.log.info("Runtime job %s submitted.", job.job_id())
        self.to_cancel.append(job)
        self.assertEqual(inputs, job.inputs)
        rjob = self.provider.runtime.job(job.job_id())
        rinterim_results = rjob.inputs['interim_results']
        self._assert_complex_types_equal(interim_results, rinterim_results)

    def test_job_backend(self):
        """Test job backend."""
        job = self._run_program()
        self.assertEqual(self.backend, job.backend())

    def test_job_program_id(self):
        """Test job program ID."""
        job = self._run_program()
        self.assertEqual(self.program_id, job.program_id)

    def test_wait_for_final_state(self):
        """Test wait for final state."""
        job = self._run_program()
        job.wait_for_final_state()
        self.assertEqual(JobStatus.DONE, job.status())

    def test_logout(self):
        """Test logout."""
        self.provider.runtime.logout()
        # Make sure we can still do things.
        self._upload_program()
        _ = self._run_program()

    def test_run_circuit(self):
        """Test run_circuit"""
        job = self.provider.run_circuits(
            ReferenceCircuits.bell(), backend=self.backend, shots=100)
        counts = job.result().get_counts()
        self.assertEqual(100, sum(counts.values()))

    def test_job_creation_date(self):
        """Test job creation date."""
        job = self._run_program(iterations=1)
        self.assertTrue(job.creation_date)
        rjob = self.provider.runtime.job(job.job_id())
        self.assertTrue(rjob.creation_date)
        rjobs = self.provider.runtime.jobs(limit=2)
        for rjob in rjobs:
            self.assertTrue(rjob.creation_date)

    def test_websocket_proxy(self):
        """Test connecting to websocket via proxy."""
        def result_callback(job_id, interim_result):  # pylint: disable=unused-argument
            nonlocal callback_called
            callback_called = True

        MockProxyServer(self, self.log).start()
        callback_called = False

        with use_proxies(self.provider, MockProxyServer.VALID_PROXIES):
            job = self._run_program(iterations=1, callback=result_callback)
            job.wait_for_final_state()

        self.assertTrue(callback_called)

    def test_websocket_proxy_invalid_port(self):
        """Test connecting to websocket via invalid proxy port."""
        def result_callback(job_id, interim_result):  # pylint: disable=unused-argument
            nonlocal callback_called
            callback_called = True

        callback_called = False
        invalid_proxy = {'https': 'http://{}:{}'.format(MockProxyServer.PROXY_IP_ADDRESS,
                                                        MockProxyServer.INVALID_PROXY_PORT)}
        with use_proxies(self.provider, invalid_proxy):
            with self.assertLogs('qiskit.providers.ibmq', 'WARNING') as log_cm:
                job = self._run_program(iterations=1, callback=result_callback)
                job.wait_for_final_state()
            self.assertIn("WebsocketError", ','.join(log_cm.output))
        self.assertFalse(callback_called)

    def test_job_logs(self):
        """Test job logs."""
        job = self._run_program(final_result="foo")
        with self.assertLogs('qiskit.providers.ibmq', 'WARN'):
            job.logs()
        job.wait_for_final_state()
        job_logs = job.logs()
        self.assertIn("this is a stdout message", job_logs)
        self.assertIn("this is a stderr message", job_logs)

    def _validate_program(self, program):
        """Validate a program."""
        self.assertTrue(program)
        self.assertTrue(program.name)
        self.assertTrue(program.program_id)
        self.assertTrue(program.description)
        self.assertTrue(program.max_execution_time)
        self.assertTrue(program.creation_date)
        self.assertTrue(program.version)

    def _upload_program(self, name=None, max_execution_time=300):
        """Upload a new program."""
        name = name or self._get_program_name()
        program_id = self.provider.runtime.upload_program(
            name=name,
            data=self.RUNTIME_PROGRAM.encode(),
            metadata=self.RUNTIME_PROGRAM_METADATA,
            max_execution_time=max_execution_time,
            description="Qiskit test program")
        self.to_delete.append(program_id)
        return program_id

    def _get_program_name(self):
        """Return a unique program name."""
        return self.PROGRAM_PREFIX + "_" + uuid.uuid4().hex

    def _assert_complex_types_equal(self, expected, received):
        """Verify the received data in complex types is expected."""
        if 'serializable_class' in received:
            received['serializable_class'] = \
                SerializableClass.from_json(received['serializable_class'])
        self.assertEqual(expected, received)

    def _run_program(self, program_id=None, iterations=1,
                     interim_results=None, final_result=None,
                     callback=None):
        """Run a program."""
        inputs = {'iterations': iterations,
                  'interim_results': interim_results or {},
                  'final_result': final_result or {}}
        pid = program_id or self.program_id
        options = {'backend_name': self.backend.name()}
        job = self.provider.runtime.run(program_id=pid, inputs=inputs,
                                        options=options, callback=callback)
        self.log.info("Runtime job %s submitted.", job.job_id())
        self.to_cancel.append(job)
        return job

    def _wait_for_status(self, job, status):
        """Wait for job to reach a certain status."""
        wait_time = 1 if status == JobStatus.QUEUED else self.poll_time
        while job.status() not in JOB_FINAL_STATES + (status,):
            time.sleep(wait_time)
        if job.status() != status:
            self.skipTest(f"Job {job.job_id()} unable to reach status {status}.")
