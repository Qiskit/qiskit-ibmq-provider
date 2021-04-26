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
from io import StringIO
from unittest.mock import patch
import uuid
import time

from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.providers.ibmq.exceptions import IBMQNotAuthorizedError
from qiskit.providers.ibmq.runtime.exceptions import (RuntimeDuplicateProgramError,
                                                      RuntimeProgramNotFound,
                                                      RuntimeJobFailureError)

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_device, requires_provider
from ..fake_runtime_client import BaseFakeRuntimeClient


@unittest.skip("Skip runtime tests")
class TestRuntime(IBMQTestCase):
    """Class for testing runtime modules."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.provider.runtime._api_client = BaseFakeRuntimeClient()

    def test_list_programs(self):
        """Test listing programs."""
        self.provider.runtime.programs()

    def test_run_program(self):
        """Test running program."""
        params = {'param1': 'foo'}
        backend = self.provider.backend.ibmq_qasm_simulator
        job = self.provider.runtime.run("QKA", backend=backend, params=params)
        self.assertTrue(job.job_id())
        self.assertIsInstance(job.status(), JobStatus)
        job.wait_for_final_state()
        self.assertEqual(job.status(), JobStatus.DONE)
        self.assertTrue(job.result())

    def test_interim_results(self):
        """Test interim results."""
        def _callback(interim_result):
            print(f"interim result {interim_result}")
        params = {'param1': 'foo'}
        backend = self.provider.backend.ibmq_qasm_simulator
        job = self.provider.runtime.run("QKA", backend=backend, params=params, callback=_callback)
        job.result()


# import random
#
# from qiskit import transpile
# from qiskit.circuit.random import random_circuit
# from qiskit.providers.ibmq.runtime.utils import RuntimeEncoder
#
# def prepare_circuits(backend):
#     circuit = random_circuit(num_qubits=5, depth=4, measure=True,
#                              seed=random.randint(0, 1000))
#     return transpile(circuit, backend)
#
# def main(backend, user_messenger, **kwargs):
#     iterations = kwargs.pop('iterations', 5)
#     interim_results = kwargs.pop('interim_results', {})
#     final_result = kwargs.pop("final_result", {})
#     for it in range(iterations):
#         qc = prepare_circuits(backend)
#         user_messenger.publish({"iteration": it, "interim_results": interim_results})
#         backend.run(qc).result()
#
#     user_messenger.publish("this is the last message")
#     print(final_result, cls=RuntimeEncoder)

@unittest.skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
class TestRuntimeIntegration(IBMQTestCase):
    """Integration tests for runtime modules."""

    RUNTIME_PROGRAM = """
import random

from qiskit import transpile
from qiskit.circuit.random import random_circuit

def prepare_circuits(backend):
    circuit = random_circuit(num_qubits=5, depth=4, measure=True,
                             seed=random.randint(0, 1000))
    return transpile(circuit, backend)

def main(backend, user_messenger, **kwargs):
    iterations = kwargs['iterations']
    interim_results = kwargs.pop('interim_results', {})
    final_result = kwargs.pop("final_result", {})
    for it in range(iterations):
        qc = prepare_circuits(backend)
        user_messenger.publish({"iteration": it, "interim_results": interim_results})
        backend.run(qc).result()

    user_messenger.publish(final_result, final=True)
    """

    PROGRAM_PREFIX = 'qiskit-test'

    @classmethod
    @requires_device
    def setUpClass(cls, backend):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.backend = backend
        cls.provider = backend.provider()
        cls.program_id = cls.PROGRAM_PREFIX
        try:
            cls.program_id = cls.provider.runtime.upload_program(
                name=cls.PROGRAM_PREFIX,
                data=cls.RUNTIME_PROGRAM.encode(),
                max_execution_time=600)
        except RuntimeDuplicateProgramError:
            pass
        except IBMQNotAuthorizedError:
            raise unittest.SkipTest("No upload access.")

    @classmethod
    def tearDownClass(cls) -> None:
        """Class level teardown."""
        super().tearDownClass()
        try:
            cls.provider.runtime.delete_program(cls.program_id)
        except Exception:  # pylint: disable=broad-except
            pass

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        self.to_delete = []
        self.to_cancel = []

    def tearDown(self) -> None:
        """Test level teardown."""
        super().tearDown()
        # Delete programs
        for prog in self.to_delete:
            try:
                self.provider.runtime.delete_program(prog)
            except Exception:  # pylint: disable=broad-except
                pass

        # Cancel jobs.
        for job in self.to_cancel:
            if job.status() not in JOB_FINAL_STATES:
                try:
                    job.cancel()
                except Exception:  # pylint: disable=broad-except
                    pass

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

    def test_print_programs(self):
        """Test printing programs."""
        programs = self.provider.runtime.programs()
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            self.provider.runtime.pprint_programs()
            stdout = mock_stdout.getvalue()
            for prog in programs:
                self.assertIn(prog.program_id, stdout)
                self.assertIn(prog.name, stdout)
                self.assertIn(prog.description, stdout)

    def test_upload_program(self):
        """Test uploading a program."""
        max_execution_time = 3000
        program_id = self._upload_program(max_execution_time=max_execution_time)
        self.assertTrue(program_id)
        program = self.provider.runtime.program(program_id)
        self.assertTrue(program)
        self.assertEqual(max_execution_time, program.max_execution_time)

    def test_upload_program_conflict(self):
        """Test uploading a program with conflicting name."""
        name = self._get_program_name()
        self._upload_program(name=name)
        with self.assertRaises(RuntimeDuplicateProgramError):
            self._upload_program(name=name)

    def test_update_program(self):
        """Test updating a program."""
        program_id = self._upload_program()
        program = self.provider.runtime.program(program_id)

        self.provider.runtime.delete_program(program_id)
        new_cost = program.max_execution_time + 1000
        new_id = self._upload_program(name=program.name, max_execution_time=new_cost)
        updated = self.provider.runtime.program(new_id, refresh=True)
        self.assertEqual(new_cost, updated.max_execution_time,
                         f"Program {new_id} does not have the expected cost.")

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
        final_result = {"string": "foo",
                        "float": 1.5,
                        "complex": 2+3j,
                        "class": self.CustomClass("foo")}
        job = self._run_program(final_result=final_result)
        result = job.result()
        my_class = self.CustomClass.from_json(result.pop('class'))
        self.assertEqual(final_result.pop('class').value, my_class.value)
        self.assertEqual(final_result, result)

    def test_run_program_failed(self):
        """Test a failed program execution."""
        options = {'backend_name': self.backend.name()}
        job = self.provider.runtime.run(program_id=self.program_id, inputs={}, options=options)
        self.log.info("Runtime job %s submitted.", job.job_id())

        job.wait_for_final_state()
        self.assertEqual(JobStatus.ERROR, job.status())
        with self.assertRaises(RuntimeJobFailureError) as err_cm:
            job.result()
        self.assertIn('KeyError', str(err_cm.exception))

    def test_retrieve_job_queued(self):
        """Test retrieving a queued job."""
        pass

    def test_retrieve_job_running(self):
        """Test retrieving a running job."""
        job = self._run_program(iterations=10)
        for _ in range(10):
            if job.status() == JobStatus.RUNNING:
                break
            time.sleep(1)
        self.assertEqual(JobStatus.RUNNING, job.status())
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(job.job_id(), rjob.job_id())

    def test_retrieve_job_done(self):
        """Test retrieving a finished job."""
        pass

    def test_cancel_job_queued(self):
        """Test canceling a queued job."""
        pass

    @unittest.skip("Skip until fixed")
    def test_cancel_job_running(self):
        """Test canceling a running job."""
        job = self._run_program(iterations=3, interim_results="foobar")
        while job.status() != JobStatus.RUNNING:
            time.sleep(5)
        job.cancel()
        self.assertEqual(job.status(), JobStatus.CANCELLED)
        rjob = self.provider.runtime.job(job.job_id())
        self.assertEqual(rjob.status(), JobStatus.CANCELLED)

    def test_cancel_job_done(self):
        """Test canceling a finished job."""
        pass

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
        self.assertIsNone(job._ws_client._ws)

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

        for _ in range(10):
            if job.status() == JobStatus.RUNNING:
                break
            time.sleep(1)
        self.assertEqual(JobStatus.RUNNING, job.status())
        job.stream_results(result_callback)
        job.wait_for_final_state()
        self.assertEqual(iterations-1, final_it)
        self.assertFalse(callback_err)
        self.assertIsNone(job._ws_client._ws)

    @unittest.skip("Skip until 267 is fixed")
    def test_stream_results_done(self):
        """Test streaming interim results after job is done."""
        def result_callback(job_id, interim_result):
            # pylint: disable=unused-argument
            nonlocal called_back
            called_back = True

        called_back = False
        job = self._run_program(interim_results="foobar")
        job.wait_for_final_state()
        job.stream_results(result_callback)
        time.sleep(1)
        self.assertFalse(called_back)
        self.assertIsNone(job._ws_client._ws)

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
        self.assertIsNone(job._ws_client._ws)

    # @unittest.skip("Skip until 277 is fixed")
    def test_callback_job_cancelled_running(self):
        """Test canceling a job while streaming results."""
        def result_callback(job_id, interim_result):
            # pylint: disable=unused-argument
            nonlocal final_it
            final_it = interim_result['iteration']

        final_it = 0
        iterations = 3
        job = self._run_program(iterations=iterations, interim_results="foo",
                                callback=result_callback)
        while job.status() != JobStatus.RUNNING:
            time.sleep(5)
        job.cancel()
        time.sleep(3)  # Wait for cleanup
        self.assertIsNone(job._ws_client._ws)
        self.assertLess(final_it, iterations)

    def test_final_result(self):
        """Test getting final result."""
        pass

    def test_job_status(self):
        """Test job status."""
        pass

    def test_job_inputs(self):
        """Test job inputs."""
        inputs = {'iterations': 1,
                  'interim_results': "foo"}
        options = {'backend_name': self.backend.name()}
        job = self.provider.runtime.run(program_id=self.program_id, inputs=inputs,
                                        options=options)
        self.log.info("Runtime job %s submitted.", job.job_id())
        self.to_cancel.append(job)
        self.assertEqual(inputs, job.inputs)

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

    def _validate_program(self, program):
        """Validate a program."""
        # TODO add more validation
        self.assertTrue(program)
        self.assertTrue(program.name)
        self.assertTrue(program.program_id)
        # self.assertTrue(program.description)
        self.assertTrue(program.max_execution_time)

    def _upload_program(self, name=None, max_execution_time=300):
        """Upload a new program."""
        name = name or self._get_program_name()
        program_id = self.provider.runtime.upload_program(
            name=name,
            data=self.RUNTIME_PROGRAM.encode(),
            max_execution_time=max_execution_time)
        self.to_delete.append(program_id)
        return program_id

    def _get_program_name(self):
        """Return a unique program name."""
        return self.PROGRAM_PREFIX + "_" + uuid.uuid4().hex

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

    # iterations = kwargs.pop('iterations', 5)
    # interim_results = kwargs.pop('interim_results', {})
    # final_result = kwargs.pop("final_result", {})
    # test_lp1_sw_renierm

    class CustomClass:
        """Custom class with serialization methods."""
        def __init__(self, value):
            self.value = value

        def to_json(self):
            """To JSON serializable."""
            return {"value": self.value}

        @classmethod
        def from_json(cls, data):
            """From JSON serializable."""
            return cls(**data)
