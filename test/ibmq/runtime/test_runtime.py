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
from unittest import mock, skipIf
import uuid
import time
import random
import subprocess
import tempfile

import numpy as np
import scipy.sparse
from qiskit.algorithms.optimizers import (
    ADAM,
    GSLS,
    IMFIL,
    SPSA,
    SNOBFIT,
    L_BFGS_B,
    NELDER_MEAD,
)
from qiskit.result import Result
from qiskit.circuit import Parameter, QuantumCircuit
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.circuit.library import EfficientSU2
from qiskit.opflow import (PauliSumOp, MatrixOp, PauliOp, CircuitOp, EvolvedOp,
                           TaperedPauliSumOp, Z2Symmetries, I, X, Y, Z,
                           StateFn, CircuitStateFn, DictStateFn, VectorStateFn, OperatorStateFn,
                           SparseVectorStateFn, CVaRMeasurement, ComposedOp, SummedOp, TensoredOp)
from qiskit.quantum_info import SparsePauliOp, Pauli, PauliTable, Statevector
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.exceptions import IBMQInputValueError
from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.runtime.utils import RuntimeEncoder, RuntimeDecoder
from qiskit.providers.ibmq.runtime import IBMRuntimeService, RuntimeJob
from qiskit.providers.ibmq.runtime.constants import API_TO_JOB_ERROR_MESSAGE
from qiskit.providers.ibmq.runtime.exceptions import (RuntimeProgramNotFound,
                                                      RuntimeJobFailureError)
from qiskit.providers.ibmq.runtime.runtime_program import (
    ParameterNamespace, ProgramParameter, ProgramResult)

from ...ibmqtestcase import IBMQTestCase
from .fake_runtime_client import (BaseFakeRuntimeClient, FailedRanTooLongRuntimeJob,
                                  FailedRuntimeJob, CancelableRuntimeJob, CustomResultRuntimeJob)
from .utils import SerializableClass, SerializableClassDecoder, get_complex_types


class TestRuntime(IBMQTestCase):
    """Class for testing runtime modules."""

    DEFAULT_METADATA = {
        "name": "qiskit-test",
        "description": "Test program.",
        "max_execution_time": 300,
        "version": "0.1",
        "backend_requirements": {"min_num_qubits":  5},
        "parameters": [
            {'name': 'param1', 'description': 'Desc 1', 'type': 'str', 'required': True},
            {'name': 'param2', 'description': 'Desc 2', 'type': 'int', 'required': False}],
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
        provider = mock.MagicMock(spec=AccountProvider)
        provider.credentials = Credentials(
            token="", url="", services={"runtime": "https://quantum-computing.ibm.com"})
        self.runtime = IBMRuntimeService(provider)
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

    def test_coder_qc(self):
        """Test runtime encoder and decoder for circuits."""
        bell = ReferenceCircuits.bell()
        unbound = EfficientSU2(num_qubits=4, reps=1, entanglement='linear')
        subtests = (
            bell,
            unbound,
            [bell, unbound]
        )
        for circ in subtests:
            with self.subTest(circ=circ):
                encoded = json.dumps(circ, cls=RuntimeEncoder)
                self.assertIsInstance(encoded, str)
                decoded = json.loads(encoded, cls=RuntimeDecoder)
                if not isinstance(circ, list):
                    decoded = [decoded]
                self.assertTrue(all(isinstance(item, QuantumCircuit) for item in decoded))

    def test_coder_operators(self):
        """Test runtime encoder and decoder for operators."""
        x = Parameter("x")
        y = x + 1
        qc = QuantumCircuit(1)
        qc.h(0)
        coeffs = np.array([1, 2, 3, 4, 5, 6])
        table = PauliTable.from_labels(["III", "IXI", "IYY", "YIZ", "XYZ", "III"])
        op = (2.0 * I ^ I)
        z2_symmetries = Z2Symmetries(
            [Pauli("IIZI"), Pauli("ZIII")], [Pauli("IIXI"), Pauli("XIII")], [1, 3], [-1, 1]
        )
        isqrt2 = 1 / np.sqrt(2)
        sparse = scipy.sparse.csr_matrix([[0, isqrt2, 0, isqrt2]])

        subtests = (
            PauliSumOp(SparsePauliOp(Pauli("XYZX"), coeffs=[2]), coeff=3),
            PauliSumOp(SparsePauliOp(Pauli("XYZX"), coeffs=[1]), coeff=y),
            PauliSumOp(SparsePauliOp(Pauli("XYZX"), coeffs=[1 + 2j]), coeff=3 - 2j),
            PauliSumOp.from_list([("II", -1.052373245772859), ("IZ", 0.39793742484318045)]),
            PauliSumOp(SparsePauliOp(table, coeffs), coeff=10),
            MatrixOp(primitive=np.array([[0, -1j], [1j, 0]]), coeff=x),
            PauliOp(primitive=Pauli("Y"), coeff=x),
            CircuitOp(qc, coeff=x),
            EvolvedOp(op, coeff=x),
            TaperedPauliSumOp(SparsePauliOp(Pauli("XYZX"), coeffs=[2]), z2_symmetries),
            StateFn(qc, coeff=x),
            CircuitStateFn(qc, is_measurement=True),
            DictStateFn("1" * 3, is_measurement=True),
            VectorStateFn(np.ones(2 ** 3, dtype=complex)),
            OperatorStateFn(CircuitOp(QuantumCircuit(1))),
            SparseVectorStateFn(sparse),
            Statevector([1, 0]),
            CVaRMeasurement(Z, 0.2),
            ComposedOp([(X ^ Y ^ Z), (Z ^ X ^ Y ^ Z).to_matrix_op()]),
            SummedOp([X ^ X * 2, Y ^ Y], 2),
            TensoredOp([(X ^ Y), (Z ^ I)]),
            (Z ^ Z) ^ (I ^ 2),
        )
        for op in subtests:
            with self.subTest(op=op):
                encoded = json.dumps(op, cls=RuntimeEncoder)
                self.assertIsInstance(encoded, str)
                decoded = json.loads(encoded, cls=RuntimeDecoder)
                self.assertEqual(op, decoded)

    @skipIf(os.name == 'nt', 'Test not supported on Windows')
    def test_coder_optimizers(self):
        """Test runtime encoder and decoder for circuits."""
        subtests = (
            (ADAM, {"maxiter": 100, "amsgrad": True}),
            (GSLS, {"maxiter": 50, "min_step_size": 0.01}),
            (IMFIL, {"maxiter": 20}),
            (SPSA, {"maxiter": 10, "learning_rate": 0.01, "perturbation": 0.1}),
            (SNOBFIT, {"maxiter": 200, "maxfail": 20}),
            # some SciPy optimizers only work with default arguments due to Qiskit/qiskit-terra#6682
            (L_BFGS_B, {}),
            (NELDER_MEAD, {}),
        )
        for opt_cls, settings in subtests:
            with self.subTest(opt_cls=opt_cls):
                optimizer = opt_cls(**settings)
                encoded = json.dumps(optimizer, cls=RuntimeEncoder)
                self.assertIsInstance(encoded, str)
                decoded = json.loads(encoded, cls=RuntimeDecoder)
                self.assertTrue(isinstance(decoded, opt_cls))
                for key, value in settings.items():
                    self.assertEqual(decoded.settings[key], value)

    def test_decoder_import(self):
        """Test runtime decoder importing modules."""
        script = """
import sys
import json
from qiskit.providers.ibmq.runtime import RuntimeDecoder
if __name__ == '__main__':
    obj = json.loads(sys.argv[1], cls=RuntimeDecoder)
    print(obj.__class__.__name__)
"""
        temp_fp = tempfile.NamedTemporaryFile(mode='w', delete=False)
        self.addCleanup(os.remove, temp_fp.name)
        temp_fp.write(script)
        temp_fp.close()

        subtests = (
            PauliSumOp(SparsePauliOp(Pauli("XYZX"), coeffs=[2]), coeff=3),
            DictStateFn("1" * 3, is_measurement=True),
            Statevector([1, 0]),
        )
        for op in subtests:
            with self.subTest(op=op):
                encoded = json.dumps(op, cls=RuntimeEncoder)
                self.assertIsInstance(encoded, str)
                cmd = ["python", temp_fp.name, encoded]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      universal_newlines=True, check=True)
                self.assertIn(op.__class__.__name__, proc.stdout)

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

    def test_program_params_validation(self):
        """Test program parameters validation process"""
        program_id = self.runtime.upload_program(
            data="foo".encode(), metadata=self.DEFAULT_METADATA)
        program = self.runtime.program(program_id)
        params: ParameterNamespace = program.parameters()
        params.param1 = 'Hello, World'
        # Check OK params
        params.validate()
        # Check OK params - contains unnecessary param
        params.param3 = 'Hello, World'
        params.validate()
        # Check bad params - missing required param
        params.param1 = None
        with self.assertRaises(IBMQInputValueError):
            params.validate()
        params.param1 = 'foo'

    def test_program_params_namespace(self):
        """Test running a program using parameter namespace."""
        program_id = self.runtime.upload_program(
            data="foo".encode(), metadata=self.DEFAULT_METADATA)
        params = self.runtime.program(program_id).parameters()
        params.param1 = "Hello World"
        self._run_program(program_id, inputs=params)

    def test_run_program_failed(self):
        """Test a failed program execution."""
        job = self._run_program(job_classes=FailedRuntimeJob)
        job.wait_for_final_state()
        job_result_raw = self.runtime._api_client.job_results(job.job_id())
        self.assertEqual(JobStatus.ERROR, job.status())
        self.assertEqual(API_TO_JOB_ERROR_MESSAGE['FAILED'].format(
            job.job_id(), job_result_raw), job.error_message())
        with self.assertRaises(RuntimeJobFailureError):
            job.result()

    def test_run_program_failed_ran_too_long(self):
        """Test a program that failed since it ran longer than maxiumum execution time."""
        job = self._run_program(job_classes=FailedRanTooLongRuntimeJob)
        job.wait_for_final_state()
        job_result_raw = self.runtime._api_client.job_results(job.job_id())
        self.assertEqual(JobStatus.ERROR, job.status())
        self.assertEqual(API_TO_JOB_ERROR_MESSAGE['CANCELLED - RAN TOO LONG'].format(
            job.job_id(), job_result_raw), job.error_message())
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

    def test_jobs_pending(self):
        """Test retrieving pending jobs (QUEUED, RUNNING)."""
        jobs = []
        program_id = self._upload_program()
        (jobs, pending_jobs_count, _) = self._populate_jobs_with_all_statuses(
            jobs=jobs, program_id=program_id)
        rjobs = self.runtime.jobs(pending=True)
        self.assertEqual(pending_jobs_count, len(rjobs))

    def test_jobs_limit_pending(self):
        """Test retrieving pending jobs (QUEUED, RUNNING) with limit."""
        jobs = []
        program_id = self._upload_program()
        (jobs, *_) = self._populate_jobs_with_all_statuses(jobs=jobs, program_id=program_id)
        limit = 4
        rjobs = self.runtime.jobs(limit=limit, pending=True)
        self.assertEqual(limit, len(rjobs))

    def test_jobs_skip_pending(self):
        """Test retrieving pending jobs (QUEUED, RUNNING) with skip."""
        jobs = []
        program_id = self._upload_program()
        (jobs, pending_jobs_count, _) = self._populate_jobs_with_all_statuses(
            jobs=jobs, program_id=program_id)
        skip = 4
        rjobs = self.runtime.jobs(skip=skip, pending=True)
        self.assertEqual(pending_jobs_count - skip, len(rjobs))

    def test_jobs_limit_skip_pending(self):
        """Test retrieving pending jobs (QUEUED, RUNNING) with limit and skip."""
        jobs = []
        program_id = self._upload_program()
        (jobs, *_) = self._populate_jobs_with_all_statuses(jobs=jobs, program_id=program_id)
        limit = 2
        skip = 3
        rjobs = self.runtime.jobs(limit=limit, skip=skip, pending=True)
        self.assertEqual(limit, len(rjobs))

    def test_jobs_returned(self):
        """Test retrieving returned jobs (COMPLETED, FAILED, CANCELLED)."""
        jobs = []
        program_id = self._upload_program()
        (jobs, _, returned_jobs_count) = self._populate_jobs_with_all_statuses(
            jobs=jobs, program_id=program_id)
        rjobs = self.runtime.jobs(pending=False)
        self.assertEqual(returned_jobs_count, len(rjobs))

    def test_jobs_limit_returned(self):
        """Test retrieving returned jobs (COMPLETED, FAILED, CANCELLED) with limit."""
        jobs = []
        program_id = self._upload_program()
        (jobs, *_) = self._populate_jobs_with_all_statuses(jobs=jobs, program_id=program_id)
        limit = 6
        rjobs = self.runtime.jobs(limit=limit, pending=False)
        self.assertEqual(limit, len(rjobs))

    def test_jobs_skip_returned(self):
        """Test retrieving returned jobs (COMPLETED, FAILED, CANCELLED) with skip."""
        jobs = []
        program_id = self._upload_program()
        (jobs, _, returned_jobs_count) = self._populate_jobs_with_all_statuses(
            jobs=jobs, program_id=program_id)
        skip = 4
        rjobs = self.runtime.jobs(skip=skip, pending=False)
        self.assertEqual(returned_jobs_count - skip, len(rjobs))

    def test_jobs_limit_skip_returned(self):
        """Test retrieving returned jobs (COMPLETED, FAILED, CANCELLED) with limit and skip."""
        jobs = []
        program_id = self._upload_program()
        (jobs, *_) = self._populate_jobs_with_all_statuses(jobs=jobs, program_id=program_id)
        limit = 6
        skip = 2
        rjobs = self.runtime.jobs(limit=limit, skip=skip, pending=False)
        self.assertEqual(limit, len(rjobs))

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
                                 program.parameters().metadata)
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

    def test_different_providers(self):
        """Test retrieving job submitted with different provider."""
        program_id = self._upload_program()
        job = self._run_program(program_id)
        cred = Credentials(token="", url="", hub="hub2", group="group2", project="project2",
                           services={"runtime": "https://quantum-computing.ibm.com"})
        self.runtime._provider.credentials = cred
        self.runtime._provider._factory = mock.MagicMock()
        rjob = self.runtime.job(job.job_id())
        self.assertIsNotNone(rjob.backend())

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

    def _run_program(self, program_id=None, inputs=None, job_classes=None, final_status=None,
                     decoder=None):
        """Run a program."""
        options = {'backend_name': "some_backend"}
        if final_status is not None:
            self.runtime._api_client.set_final_status(final_status)
        elif job_classes:
            self.runtime._api_client.set_job_classes(job_classes)
        if program_id is None:
            program_id = self._upload_program()
        job = self.runtime.run(program_id=program_id, inputs=inputs,
                               options=options, result_decoder=decoder)
        return job

    def _populate_jobs_with_all_statuses(self, jobs, program_id):
        pending_jobs_count = 0
        returned_jobs_count = 0
        for _ in range(3):
            jobs.append(self._run_program(program_id, final_status='RUNNING'))
            pending_jobs_count += 1
        for _ in range(4):
            jobs.append(self._run_program(program_id, final_status='COMPLETED'))
            returned_jobs_count += 1
        for _ in range(2):
            jobs.append(self._run_program(program_id, final_status='QUEUED'))
            pending_jobs_count += 1
        for _ in range(3):
            jobs.append(self._run_program(program_id, final_status='FAILED'))
            returned_jobs_count += 1
        for _ in range(2):
            jobs.append(self._run_program(program_id, final_status='CANCELLED'))
            returned_jobs_count += 1
        return (jobs, pending_jobs_count, returned_jobs_count)
