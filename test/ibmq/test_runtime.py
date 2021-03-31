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
            self.assertTrue(prog.name)
