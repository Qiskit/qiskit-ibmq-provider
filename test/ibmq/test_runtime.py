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

from qiskit.providers.jobstatus import JobStatus

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider
from ..fake_runtime_client import BaseFakeRuntimeClient


@unittest.skip("Skip runtime tests")
class TestRuntime(IBMQTestCase):

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
        def _callback(interim_result):
            print(f"interim result {interim_result}")
        params = {'param1': 'foo'}
        backend = self.provider.backend.ibmq_qasm_simulator
        job = self.provider.runtime.run("QKA", backend=backend, params=params, callback=_callback)
        job.result()


@unittest.skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
class TestRuntimeIntegration(IBMQTestCase):

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        try:
            provider.runtime.programs()
        except Exception:
            raise unittest.SkipTest("No access to runtime service.")

    def test_list_programs(self):
        """Test listing programs."""
        programs = self.provider.runtime.programs()
        self.assertTrue(programs)
        for prog in programs:
            self._validate_program(prog)

    def test_list_program(self):
        """Test listing a single program."""
        program = self.provider.runtime.programs()[0]
        self._validate_program(program)

    def test_print_programs(self):
        """Test printing programs."""
        programs = self.provider.runtime.programs()
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            self.provider.runtime.pprint_programs()
            for prog in programs:
                self.assertIn(prog.program_id, mock_stdout)
                self.assertIn(prog.name, mock_stdout)
                self.assertIn(prog.description, mock_stdout)

    def test_upload_program(self):
        """Test uploading a program."""
        pass

    def test_upload_program_conflict(self):
        """Test uploading a program with conflicting name."""
        pass

    def test_upload_program_missing(self):
        pass

    def test_execute_program(self):
        pass

    def test_execute_program_bad_params(self):
        pass

    def test_execute_program_failed(self):
        pass

    def _validate_program(self, program):
        self.assertTrue(program)
        self.assertTrue(program.name)
        self.assertTrue(program.program_id)
        self.assertTrue(program.description)
        self.assertTrue(program.cost)
