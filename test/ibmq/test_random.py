# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for random number services."""

import time
import uuid
from unittest import skipIf
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.random.cqcextractor import CQCExtractor
from qiskit.providers.ibmq.random.utils import bitarray_to_bytes
from qiskit.providers.ibmq.random.ibmqrandomservice import IBMQRandomService
from qiskit.providers.ibmq.exceptions import IBMQError

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider

HAS_QISKIT_RNG = True
try:
    from qiskit_rng import Generator
except ImportError:
    HAS_QISKIT_RNG = False


@skipIf(not HAS_QISKIT_RNG, 'qiskit_rng is needed for this test.')
class TestRandomIntegration(IBMQTestCase):
    """Integration tests for random number services."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider

    def can_access_extractor(self):
        """Return whether there is access to the CQC extractors."""
        try:
            self.provider.random.get_service('cqc_extractor')
            return True
        except IBMQError:
            return False

    def test_cqc_extractor(self):
        """Test invoking the CQC extractors."""
        generator = Generator(self.provider.get_backend('ibmq_qasm_simulator'))
        output = generator.sample(1024).block_until_ready()
        params = output.get_cqc_extractor_params()

        if not self.can_access_extractor():
            self.skipTest("No access to CQC extractor")

        extractor = self.provider.random.cqc_extractor
        job1 = extractor.run_async_ext1(params.ext1_input_num_bits, params.ext1_output_num_bits,
                                        params.ext1_raw_bytes, params.ext1_wsr_bytes)
        self.assertEqual(job1.extractor_method, 'ext1')
        self.assertEqual(job1.parameters['ext1_input_num_bits'], params.ext1_input_num_bits)
        self.assertEqual(job1.parameters['ext1_output_num_bits'], params.ext1_output_num_bits)
        self.assertEqual(job1.parameters['ext1_wsr_bytes'], params.ext1_wsr_bytes)
        self.assertEqual(job1.parameters['ext1_raw_bytes'], params.ext1_raw_bytes)
        self.log.debug("Waiting for extractor 1 to finish.")
        ext1_out = job1.block_until_ready(timeout=300)
        self.assertIsInstance(ext1_out, list)
        self.assertEqual(len(ext1_out), params.ext1_output_num_bits)

        job2 = extractor.run_async_ext2(ext1_out, params.ext2_seed_num_bits,
                                        params.ext2_wsr_multiplier)
        self.assertEqual(job2.extractor_method, 'ext2')
        self.assertEqual(job2.parameters['ext2_wsr_multiplier'], params.ext2_wsr_multiplier)
        self.assertEqual(job2.parameters['ext2_seed_num_bits'], params.ext2_seed_num_bits)
        self.assertEqual(job2.parameters['ext2_seed_bytes'],
                         bitarray_to_bytes(ext1_out[:params.ext2_seed_num_bits]))
        self.log.debug("Waiting for extractor 2 to finish.")
        ext2_out = job2.block_until_ready(timeout=300)
        self.assertIsInstance(ext2_out, list)

        final_out = np.append(ext1_out, ext2_out).tolist()
        c_out = extractor.run(*params)
        self.assertIsInstance(c_out, list)
        self.assertEqual(len(final_out), len(c_out))


class TestRandom(IBMQTestCase):
    """Tests for random number services."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        random_service = IBMQRandomService(provider)  # pylint: disable=no-value-for-parameter
        random_service._random_client = FakeRandomClient()
        random_service._initialized = False
        cls.provider._random = random_service

    def test_list_random_services(self):
        """Test listing random number services."""
        random_services = self.provider.random.services()
        cqc_found = False
        for service in random_services:
            if service.name == 'cqc_extractor':
                self.assertIsInstance(service, CQCExtractor)
                cqc_found = True
        self.assertTrue(cqc_found, "CQC extractor not found.")

    def test_get_random_service(self):
        """Test retrieving a specific service."""
        self.assertIsInstance(self.provider.random.get_service('cqc_extractor'), CQCExtractor)
        self.assertIsInstance(self.provider.random.cqc_extractor, CQCExtractor)

    def test_extractor_sync_run_ext1(self):
        """Test invoking extractor 1 synchronously."""
        extractor = self.provider.random.get_service('cqc_extractor')
        some_int = 42
        some_byte = some_int.to_bytes(1, 'big')
        output = extractor.run(5, 8, some_byte, some_byte, 0, 0)
        self.assertIsInstance(output, list)
        self.assertEqual(output, FakeRandomClient.RESULT)

    def test_extractor_sync_run_both(self):
        """Test invoking both extractors synchronously."""
        extractor = self.provider.random.get_service('cqc_extractor')
        some_int = 42
        some_byte = some_int.to_bytes(1, 'big')
        output = extractor.run(5, 8, some_byte, some_byte, 8, 2)
        self.assertIsInstance(output, list)
        self.assertEqual(output, FakeRandomClient.RESULT*2)

    def test_extractor_async_ext1(self):
        """Test invoking extractor 1 asynchronously."""
        extractor = self.provider.random.get_service('cqc_extractor')
        some_int1 = 42
        some_int2 = 24
        some_byte1 = some_int1.to_bytes(1, 'big')
        some_byte2 = some_int2.to_bytes(1, 'big')
        job = extractor.run_async_ext1(5, 8, some_byte1, some_byte2)
        self.assertEqual(job.parameters['ext1_input_num_bits'], 5)
        self.assertEqual(job.parameters['ext1_output_num_bits'], 8)
        self.assertEqual(job.parameters['ext1_raw_bytes'], some_byte1)
        self.assertEqual(job.parameters['ext1_wsr_bytes'], some_byte2)
        self.assertEqual(job.extractor_method, 'ext1')
        result = job.block_until_ready()
        self.assertEqual(job.status(), JobStatus.DONE)
        self.assertEqual(result, FakeRandomClient.RESULT)

    def test_extractor_async_ext2(self):
        """Test invoking extractor 2 asynchronously."""
        extractor = self.provider.random.get_service('cqc_extractor')
        seed = list(np.random.randint(2, size=8))

        job = extractor.run_async_ext2(seed, len(seed), 2)
        self.assertEqual(job.parameters['ext2_seed_num_bits'], len(seed))
        self.assertEqual(job.parameters['ext2_wsr_multiplier'], 2)
        self.assertEqual(job.parameters['ext2_seed_bytes'], bitarray_to_bytes(seed))
        self.assertEqual(job.extractor_method, 'ext2')
        result = job.block_until_ready()
        self.assertEqual(job.status(), JobStatus.DONE)
        self.assertEqual(result, FakeRandomClient.RESULT)


class FakeRandomClient:
    """Client to return fake extractor data."""

    RESULT = [0, 1, 0, 1, 0, 1, 0, 1]

    def __init__(self):
        self._executor = ThreadPoolExecutor()
        self._jobs = {}

    def list_services(self):
        """Return fake random services."""
        return [{'name': 'cqc', 'extractors': ['ext1', 'ext2']}]

    def extract(self, name, method, data, files):
        """Return fake random output."""
        # pylint: disable=unused-argument
        job_id = uuid.uuid4().hex
        new_job = BaseFakeJob(self._executor, job_id, method, data, files)
        self._jobs[job_id] = new_job
        return new_job.job_data(include_result=False)

    def job_get(self, job_id):
        """Return fake job data."""
        return self._jobs.get(job_id).job_data()

    def get_object_storage(self, url):
        """Return fake data."""
        if url == 'fake_result_url':
            return bitarray_to_bytes(self.RESULT)
        return bitarray_to_bytes([1, 1, 1])


class BaseFakeJob:
    """Base class for faking a remote job."""

    _job_progress = [
        'RUNNING',
        'COMPLETED'
    ]

    def __init__(self, executor, job_id, method, data, files):
        """Initialize a fake job."""
        self._job_id = job_id
        self._status = 'RUNNING'
        self._method = method
        if method == 'ext1':
            self._params = {'x': 'fake_x_url', 'y': 'fake_y_url'}
        else:
            self._params = {'r': 'fake_r_url', 'x': 'fake_x_url'}
        self._params.update(data)
        self._data = data
        self._files = files
        self._future = executor.submit(self._auto_progress)

    def _auto_progress(self):
        """Automatically update job status."""
        for status in self._job_progress:
            time.sleep(1)
            self._status = status

    def job_data(self, include_result=True):
        """Return current job data."""
        status = self._status
        data = {'id': self._job_id, 'status': status, 'parameters': self._params}
        if status == 'COMPLETED' and include_result:
            data['result'] = 'fake_result_url'
        return data
