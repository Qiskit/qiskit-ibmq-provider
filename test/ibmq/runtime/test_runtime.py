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

import json
import os
from io import StringIO
from unittest.mock import patch
from unittest import mock
import uuid
import time
import random

import numpy as np
from qiskit.result import Result
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.runtime.utils import RuntimeEncoder, RuntimeDecoder
from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.ibmq.runtime import IBMRuntimeService, RuntimeJob
from qiskit.providers.ibmq.runtime.exceptions import (RuntimeProgramNotFound,
                                                      RuntimeJobFailureError)
from qiskit.providers.ibmq.runtime.runtime_program import ProgramParameter, ProgramResult


from ...ibmqtestcase import IBMQTestCase
from .fake_runtime_client import (BaseFakeRuntimeClient, FailedRuntimeJob, CancelableRuntimeJob,
                                  CustomResultRuntimeJob)
from .utils import (SerializableClass, UnserializableClass, SerializableClassDecoder,
                    get_complex_types)


class TestRuntime(IBMQTestCase):
    """Class for testing runtime modules."""

    DEFAULT_METADATA = {
        "name": "qiskit-test",
        "description": "Test program.",
        "max_execution_time": 300,
        "version": "0.1",
        "backend_requirements": {"min_num_qubits":  5},
        "parameters": [
            {"name": "param1", "description": "Some parameter.",
             "type": "integer", "required": True}
        ],
        "return_values": [
            {"name": "ret_val", "description": "Some return value.", "type": "string"}
        ],
        "interim_results": [
            {"name": "int_res", "description": "Some interim result", "type": "string"},
        ]
    }

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.runtime = IBMRuntimeService(mock.MagicMock(sepc=AccountProvider))
        self.runtime._api_client = BaseFakeRuntimeClient()

    def test_coder(self):
        """Test runtime encoder and decoder."""
        result = Result(backend_name='ibmqx2',
                        backend_version='1.1',
                        qobj_id='12345',
                        job_id='67890',
                        success=False,
                        results=[])

        data = {"string": "foo",
                "float": 1.5,
                "complex": 2+3j,
                "array": np.array([[1, 2, 3], [4, 5, 6]]),
                "result": result,
                "sclass": SerializableClass("foo"),
                "usclass": UnserializableClass("bar"),
                }
        encoded = json.dumps(data, cls=RuntimeEncoder)
        decoded = json.loads(encoded, cls=RuntimeDecoder)
        decoded["sclass"] = SerializableClass.from_json(decoded['sclass'])

        decoded_result = decoded.pop('result')
        data.pop('result')

        decoded_array = decoded.pop('array')
        orig_array = data.pop('array')

        self.assertEqual(decoded, data)
        self.assertIsInstance(decoded_result, Result)
        self.assertTrue((decoded_array == orig_array).all())

    def test_list_programs(self):
        """Test listing programs."""
        program_id = self._upload_program()
        programs = self.runtime.programs()
        all_ids = [prog.program_id for prog in programs]
        self.assertIn(program_id, all_ids)

    def test_list_program(self):
        """Test listing a single program."""
        program_id = self._upload_program()
        program = self.runtime.program(program_id)
        self.assertEqual(program_id, program.program_id)

    def test_print_programs(self):
        """Test printing programs."""
        ids = []
        for idx in range(3):
            ids.append(self._upload_program(name=f"name_{idx}"))

        programs = self.runtime.programs()
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            self.runtime.pprint_programs()
            stdout = mock_stdout.getvalue()
            for prog in programs:
                self.assertIn(prog.program_id, stdout)
                self.assertIn(prog.name, stdout)

    def test_upload_program(self):
        """Test uploading a program."""
        max_execution_time = 3000
        program_id = self._upload_program(max_execution_time=max_execution_time)
        self.assertTrue(program_id)
        program = self.runtime.program(program_id)
        self.assertTrue(program)
        self.assertEqual(max_execution_time, program.max_execution_time)

    def test_delete_program(self):
        """Test deleting program."""
        program_id = self._upload_program()
        self.runtime.delete_program(program_id)
        with self.assertRaises(RuntimeProgramNotFound):
            self.runtime.program(program_id, refresh=True)

    def test_double_delete_program(self):
        """Test deleting a deleted program."""
        program_id = self._upload_program()
        self.runtime.delete_program(program_id)
        with self.assertRaises(RuntimeProgramNotFound):
            self.runtime.delete_program(program_id)

    def test_run_program(self):
        """Test running program."""
        params = {'param1': 'foo'}
        job = self._run_program(inputs=params)
        self.assertTrue(job.job_id())
        self.assertIsInstance(job, RuntimeJob)
        self.assertIsInstance(job.status(), JobStatus)
        self.assertEqual(job.inputs, params)
        job.wait_for_final_state()
        self.assertEqual(job.status(), JobStatus.DONE)
        self.assertTrue(job.result())

    def test_run_program_failed(self):
        """Test a failed program execution."""
        job = self._run_program(job_classes=FailedRuntimeJob)
        job.wait_for_final_state()
        self.assertEqual(JobStatus.ERROR, job.status())
        with self.assertRaises(RuntimeJobFailureError):
            job.result()

    def test_retrieve_job(self):
        """Test retrieving a job."""
        program_id = self._upload_program()
        params = {'param1': 'foo'}
        job = self._run_program(program_id, inputs=params)
        rjob = self.runtime.job(job.job_id())
        self.assertEqual(job.job_id(), rjob.job_id())
        self.assertEqual(program_id, rjob.program_id)

    def test_jobs_no_limit(self):
        """Test retrieving jobs without limit."""
        jobs = []
        program_id = self._upload_program()
        for _ in range(25):
            jobs.append(self._run_program(program_id))
        rjobs = self.runtime.jobs(limit=None)
        self.assertEqual(25, len(rjobs))

    def test_jobs_limit(self):
        """Test retrieving jobs with limit."""
        jobs = []
        job_count = 25
        program_id = self._upload_program()
        for _ in range(job_count):
            jobs.append(self._run_program(program_id))

        limits = [21, 30]
        for limit in limits:
            with self.subTest(limit=limit):
                rjobs = self.runtime.jobs(limit=limit)
                self.assertEqual(min(limit, job_count), len(rjobs))

    def test_jobs_skip(self):
        """Test retrieving jobs with skip."""
        jobs = []
        program_id = self._upload_program()
        for _ in range(5):
            jobs.append(self._run_program(program_id))
        rjobs = self.runtime.jobs(skip=4)
        self.assertEqual(1, len(rjobs))

    def test_jobs_skip_limit(self):
        """Test retrieving jobs with skip and limit."""
        jobs = []
        program_id = self._upload_program()
        for _ in range(10):
            jobs.append(self._run_program(program_id))
        rjobs = self.runtime.jobs(skip=4, limit=2)
        self.assertEqual(2, len(rjobs))

    def test_cancel_job(self):
        """Test canceling a job."""
        job = self._run_program(job_classes=CancelableRuntimeJob)
        time.sleep(1)
        job.cancel()
        self.assertEqual(job.status(), JobStatus.CANCELLED)
        rjob = self.runtime.job(job.job_id())
        self.assertEqual(rjob.status(), JobStatus.CANCELLED)

    def test_final_result(self):
        """Test getting final result."""
        job = self._run_program()
        result = job.result()
        self.assertTrue(result)

    def test_job_status(self):
        """Test job status."""
        job = self._run_program()
        time.sleep(random.randint(1, 5))
        self.assertTrue(job.status())

    def test_job_inputs(self):
        """Test job inputs."""
        inputs = {"param1": "foo", "param2": "bar"}
        job = self._run_program(inputs=inputs)
        self.assertEqual(inputs, job.inputs)

    def test_job_program_id(self):
        """Test job program ID."""
        program_id = self._upload_program()
        job = self._run_program(program_id=program_id)
        self.assertEqual(program_id, job.program_id)

    def test_wait_for_final_state(self):
        """Test wait for final state."""
        job = self._run_program()
        job.wait_for_final_state()
        self.assertEqual(JobStatus.DONE, job.status())

    def test_result_decoder(self):
        """Test result decoder."""
        custom_result = get_complex_types()
        job_cls = CustomResultRuntimeJob
        job_cls.custom_result = custom_result

        sub_tests = [(SerializableClassDecoder, None), (None, SerializableClassDecoder)]
        for result_decoder, decoder in sub_tests:
            with self.subTest(decoder=decoder):
                job = self._run_program(job_classes=job_cls, decoder=result_decoder)
                result = job.result(decoder=decoder)
                self.assertIsInstance(result['serializable_class'], SerializableClass)

    def test_program_metadata(self):
        """Test program metadata."""
        file_name = "test_metadata.json"
        with open(file_name, 'w') as file:
            json.dump(self.DEFAULT_METADATA, file)
        self.addCleanup(os.remove, file_name)

        sub_tests = [file_name, self.DEFAULT_METADATA]

        for metadata in sub_tests:
            with self.subTest(metadata_type=type(metadata)):
                program_id = self.runtime.upload_program(data="foo".encode(), metadata=metadata)
                program = self.runtime.program(program_id)
                self.runtime.delete_program(program_id)
                self.assertEqual(self.DEFAULT_METADATA['name'], program.name)
                self.assertEqual(self.DEFAULT_METADATA['description'], program.description)
                self.assertEqual(self.DEFAULT_METADATA['max_execution_time'],
                                 program.max_execution_time)
                self.assertEqual(self.DEFAULT_METADATA["version"], program.version)
                self.assertEqual(self.DEFAULT_METADATA['backend_requirements'],
                                 program.backend_requirements)
                self.assertEqual([ProgramParameter(**param) for param in
                                  self.DEFAULT_METADATA['parameters']],
                                 program.parameters)
                self.assertEqual([ProgramResult(**ret) for ret in
                                  self.DEFAULT_METADATA['return_values']],
                                 program.return_values)
                self.assertEqual([ProgramResult(**ret) for ret in
                                  self.DEFAULT_METADATA['interim_results']],
                                 program.interim_results)

    def test_metadata_combined(self):
        """Test combining metadata"""
        update_metadata = {"version": "1.2", "max_execution_time": 600}
        program_id = self.runtime.upload_program(
            data="foo".encode(), metadata=self.DEFAULT_METADATA, **update_metadata)
        program = self.runtime.program(program_id)
        self.assertEqual(update_metadata['max_execution_time'], program.max_execution_time)
        self.assertEqual(update_metadata["version"], program.version)

    def _upload_program(self, name=None, max_execution_time=300):
        """Upload a new program."""
        name = name or uuid.uuid4().hex
        data = "def main() {}"
        program_id = self.runtime.upload_program(
            name=name,
            data=data.encode(),
            max_execution_time=max_execution_time,
            description="A test program")
        return program_id

    def _run_program(self, program_id=None, inputs=None, job_classes=None, decoder=None):
        """Run a program."""
        options = {'backend_name': "some_backend"}
        if job_classes:
            self.runtime._api_client.set_job_classes(job_classes)
        if program_id is None:
            program_id = self._upload_program()
        job = self.runtime.run(program_id=program_id, inputs=inputs,
                               options=options, result_decoder=decoder)
        return job
