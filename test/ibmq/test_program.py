# -*- coding: utf-8 -*-

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

"""Program Test."""

import time
import copy
from datetime import datetime, timedelta
from unittest import SkipTest
from threading import Thread, Event

from ..ibmqtestcase import IBMQTestCase
from ..decorators import (requires_provider, requires_device)
from ..utils import (most_busy_backend, get_large_circuit, bell_in_qobj, cancel_job,
                     submit_job_bad_shots, submit_and_cancel, submit_job_one_bad_instr)


class TestProgram(IBMQTestCase):
    """Test ibmqjob module."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.programs = None

    def test_get_programs(self):
        """Test retrieve all programs."""
        programs = self._retrieve_and_cache_programs()
        self.assertTrue(programs, "No programs found.")

    def test_get_programs_with_backend(self):
        """Test retrieve all programs for a specific backend."""
        programs = self._retrieve_and_cache_programs()
        backend_name = programs[0].backend_name
        uuid = programs[0].uuid
        backend_programs = self.provider.backends.programs(backend_name=backend_name)

        found = False
        for prog in backend_programs:
            self.assertEqual(prog.backend_name, backend_name)
            if prog.uuid == uuid:
                found = True
        self.assertTrue(found, "Program {} not found when filter by backend name {}.".format(
            uuid, backend_name))

    def test_retrieve_program(self):
        """Test retrieve a program by its ID."""
        programs = self._retrieve_and_cache_programs()
        prog = programs[0]
        rprog = self.provider.backends.retrieve_program(prog.uuid)
        self.assertEqual(prog.uuid, rprog.uuid)

    def _retrieve_and_cache_programs(self):
        if not self.programs:
            self.programs = self.provider.backends.programs()
        return self.programs
