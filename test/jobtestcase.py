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

"""Custom TestCase for Jobs."""

import time

from qiskit.providers import JobStatus

from .ibmqtestcase import IBMQTestCase


class JobTestCase(IBMQTestCase):
    """Include common functionality when testing jobs."""

    def wait_for_initialization(self, job, timeout=1):
        """Waits until job progresses from `INITIALIZING` to other status."""
        waited = 0
        wait = 0.1
        while job.status() is JobStatus.INITIALIZING:
            time.sleep(wait)
            waited += wait
            if waited > timeout:
                self.fail(
                    msg="The JOB is still initializing after timeout ({}s)"
                    .format(timeout)
                )
