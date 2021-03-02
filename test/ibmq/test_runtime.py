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

"""Tests for random number services."""

import time
import uuid
from unittest import skipIf
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.exceptions import IBMQError

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


class TestRuntime(IBMQTestCase):

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider

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
